from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import httpx
import jsonschema

from benchmark.config import request_headers, target_config
from benchmark.io import fingerprint, utcnow


READ_ONLY_ENDPOINTS = ("read", "cpu")


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
        return {
            k: normalize(v, ignored)
            for k, v in sorted(value.items())
            if k not in ignored
        }
    if isinstance(value, list):
        return [normalize(v, ignored) for v in value]
    return value


def _openapi_contract(spec: dict, endpoints: dict) -> dict:
    paths = spec["paths"]
    selected = {}

    for name, endpoint in endpoints.items():
        # OpenAPI paths do not contain query strings.
        path = urlsplit(endpoint["path"]).path
        operation = paths[path][endpoint["method"].lower()]
        selected[name] = {
            key: operation.get(key)
            for key in ("requestBody", "responses", "parameters", "security")
        }

    return normalize(
        {
            "operations": selected,
            "schemas": spec.get("components", {}).get("schemas", {}),
        },
        ["description", "summary", "title", "example", "examples"],
    )


def validate_contracts(
    c: dict,
    *,
    models: list[str] | None = None,
    endpoints: list[str] | None = None,
    client: httpx.Client | None = None,
) -> dict:
    """Validate read-only runtime contracts; never sends benchmark writes."""
    selected_models = list(models or c["targets"]["targets"])
    selected_endpoints = list(endpoints or READ_ONLY_ENDPOINTS)

    invalid_models = set(selected_models) - set(c["targets"]["targets"])
    invalid_endpoints = set(selected_endpoints) - set(READ_ONLY_ENDPOINTS)

    report: dict = {
        "timestamp": utcnow(),
        "passed": False,
        "models": {},
        "errors": [],
        "scope": {
            "models": selected_models,
            "runtime_endpoints": selected_endpoints,
            "writes_executed": False,
            "equivalence_checked": len(selected_models) == 3,
        },
    }

    if invalid_models:
        report["errors"].append("Danh sách target không hợp lệ")
        return report
    if invalid_endpoints:
        report["errors"].append("Validator chỉ hỗ trợ endpoint read-only: read, cpu")
        return report

    owns_client = client is None
    client = client or httpx.Client(
        timeout=c["targets"]["timeout_seconds"],
        follow_redirects=False,
    )

    contracts: dict = {}
    payloads: dict = {}

    try:
        for model in selected_models:
            model_report = {
                "checks": [],
                "timeout_seconds": c["targets"]["timeout_seconds"],
                "auth": (
                    "bearer_env"
                    if "Authorization" in request_headers(c, model)
                    else "none"
                ),
            }
            report["models"][model] = model_report

            try:
                target = target_config(c, model)
                if not target["url"]:
                    raise ValueError("Target URL chưa được cấu hình")

                headers = request_headers(c, model)
                openapi_url = target["url"] + c["targets"]["openapi_path"]

                response = client.get(openapi_url, headers=headers)
                response.raise_for_status()
                spec = response.json()

                # Inspect all configured OpenAPI operations, including write,
                # but never execute a write request.
                contracts[model] = _openapi_contract(
                    spec,
                    c["targets"]["endpoints"],
                )
                model_report["contract_hash"] = fingerprint(contracts[model])

                outputs = {}

                for name in selected_endpoints:
                    endpoint = c["targets"]["endpoints"][name]

                    if name == "read":
                        trials = list(c["targets"]["read_ids"])
                    else:
                        # Two identical GET requests verify deterministic output.
                        trials = ["cpu-trial-1", "cpu-trial-2"]

                    outputs[name] = []

                    for trial in trials:
                        replacements = {
                            "id": trial,
                            "item_id": trial,
                            "run_id": "read-only-compatibility",
                            "write_id": "not-used",
                        }
                        path = substitute(endpoint["path"], replacements)
                        url = target["url"] + path

                        # The selected endpoint set is restricted to GET.
                        if endpoint["method"].upper() != "GET":
                            raise ValueError("Read-only validator rejected non-GET")

                        result = client.get(url, headers=headers)

                        if result.status_code not in endpoint["expected_status"]:
                            raise ValueError(f"{name}: unexpected HTTP status")

                        payload = result.json()
                        jsonschema.validate(
                            payload,
                            endpoint["response_schema"],
                        )

                        if (
                            endpoint.get("success_field")
                            and payload.get(endpoint["success_field"])
                            != endpoint["success_value"]
                        ):
                            raise ValueError(f"{name}: business check failed")

                        outputs[name].append(
                            normalize(payload, endpoint.get("ignore_fields", []))
                        )

                    if name == "cpu" and len(set(
                        fingerprint(item) for item in outputs[name]
                    )) != 1:
                        raise ValueError("CPU response is not deterministic")

                    model_report["checks"].append(
                        {
                            "endpoint": name,
                            "method": "GET",
                            "passed": True,
                            "trials": len(trials),
                        }
                    )

                payloads[model] = outputs

            except (
                httpx.HTTPError,
                ValueError,
                KeyError,
                TypeError,
                jsonschema.ValidationError,
                jsonschema.SchemaError,
            ) as error:
                # Never include URLs, tokens, response bodies or query strings.
                report["errors"].append(
                    f"{model}: {type(error).__name__}: contract/status/schema check failed"
                )

        # Compare deployments only when all three were explicitly selected.
        if len(selected_models) == 3:
            for collection, label in (
                (contracts, "OpenAPI"),
                (payloads, "read-only payload"),
            ):
                if (
                    len(collection) != 3
                    or len({fingerprint(value) for value in collection.values()}) != 1
                ):
                    report["errors"].append(
                        f"{label}: equivalence across all three deployments not verified"
                    )

        report["passed"] = not report["errors"]

    finally:
        if owns_client:
            client.close()

    return report
