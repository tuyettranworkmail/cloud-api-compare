"""Contract validation runs against every model before any comparative run."""
from __future__ import annotations

import copy
import uuid
from typing import Any

import httpx
import jsonschema

from benchmark.config import request_headers, target_config
from benchmark.io import fingerprint, utcnow


def substitute(value: Any, replacements: dict) -> Any:
    if isinstance(value, str):
        for key, replacement in replacements.items():
            value = value.replace("{" + key + "}", str(replacement))
        return value
    if isinstance(value, dict):
        return {k: substitute(v, replacements) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute(v, replacements) for v in value]
    return value


def normalize(value: Any, ignored: list[str]) -> Any:
    if isinstance(value, dict):
        return {k: normalize(v, ignored) for k, v in sorted(value.items()) if k not in ignored}
    if isinstance(value, list):
        return [normalize(v, ignored) for v in value]
    return value


def validate_contracts(c: dict, *, allow_writes: bool = False, client: httpx.Client | None = None) -> dict:
    report: dict = {"timestamp": utcnow(), "passed": False, "models": {}, "errors": [], "scope": "all read_ids; two deterministic CPU trials; schema and normalized write response"}
    owns = client is None
    client = client or httpx.Client(timeout=c["targets"]["timeout_seconds"], follow_redirects=False)
    payloads: dict = {}
    contracts: dict = {}
    try:
        for model in c["targets"]["targets"]:
            target = target_config(c, model)
            model_report: dict = {"checks": [], "timeout_seconds": c["targets"]["timeout_seconds"], "auth": "bearer_env" if "Authorization" in request_headers(c, model) else "none"}
            report["models"][model] = model_report
            if not target["url"]:
                report["errors"].append(f"{model}: URL chưa được cấu hình")
                continue
            try:
                r = client.get(target["url"] + c["targets"]["openapi_path"], headers=request_headers(c, model))
                r.raise_for_status()
                spec = r.json()
                paths = spec["paths"]
                # Exclude documentation differences while comparing all referenced component schemas.
                selected = {}
                for name, ep in c["targets"]["endpoints"].items():
                    operation = paths[ep["path"]][ep["method"].lower()]
                    selected[name] = {k: operation.get(k) for k in ("requestBody", "responses", "parameters", "security")}
                contracts[model] = normalize({"operations": selected, "schemas": spec.get("components", {}).get("schemas", {})}, ["description", "summary", "title", "example", "examples"])
                model_report["contract_hash"] = fingerprint(contracts[model])
                outputs = {}
                for name, ep in c["targets"]["endpoints"].items():
                    if name == "write" and not allow_writes:
                        raise ValueError("Smoke test ghi cần safety.allow_benchmark_writes=true")
                    trials = c["targets"]["read_ids"] if name == "read" else ["trial-1", "trial-2"] if name == "cpu" else ["trial-1"]
                    outputs[name] = []
                    for item_id in trials:
                        replacements = {"id": item_id, "run_id": "compatibility", "write_id": "bench-compat-" + uuid.uuid4().hex}
                        body = substitute(copy.deepcopy(ep.get("body")), replacements)
                        response = client.request(ep["method"], target["url"] + substitute(ep["path"], replacements), json=body if body is not None else None, headers=request_headers(c, model))
                        if response.status_code not in ep["expected_status"]:
                            raise ValueError(f"{name}: HTTP {response.status_code}")
                        payload = response.json()
                        jsonschema.validate(payload, ep["response_schema"])
                        if ep.get("success_field") and payload.get(ep["success_field"]) != ep["success_value"]:
                            raise ValueError(f"{name}: business failure")
                        outputs[name].append(normalize(payload, ep.get("ignore_fields", [])))
                    if name == "cpu" and outputs[name][0] != outputs[name][1]:
                        raise ValueError("CPU không xác định với cùng input")
                    model_report["checks"].append({"endpoint": name, "passed": True, "trials": len(trials)})
                payloads[model] = outputs
            except (httpx.HTTPError, ValueError, KeyError, jsonschema.ValidationError, jsonschema.SchemaError) as error:
                # Avoid response content, URL query strings and authorization in diagnostics.
                report["errors"].append(f"{model}: {type(error).__name__}: contract/status/schema không đạt")
        for collection, label in ((contracts, "OpenAPI"), (payloads, "payload/CPU")):
            if len(collection) != 3 or len({fingerprint(v) for v in collection.values()}) != 1:
                report["errors"].append(f"{label}: chưa xác minh tương đương giữa ba deployment")
        report["passed"] = not report["errors"]
    finally:
        if owns:
            client.close()
    return report
