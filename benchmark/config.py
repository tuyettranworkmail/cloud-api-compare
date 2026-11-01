from __future__ import annotations

import copy
import math
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml
from dotenv import load_dotenv


class ConfigError(ValueError):
    pass


def load_config(directory: str | Path = "configs") -> dict[str, Any]:
    load_dotenv(override=False)
    root = Path(directory)
    config = {}
    for name in ("targets", "workloads", "experiments"):
        config[name] = yaml.safe_load((root / f"{name}.yaml").read_text(encoding="utf-8"))
    validate_config(config)
    return config


def validate_config(c: dict[str, Any]) -> None:
    t, w, e = c["targets"], c["workloads"], c["experiments"]
    if set(t["targets"]) != {"iaas", "paas", "faas"}:
        raise ConfigError("Cần đủ iaas, paas, faas")
    if set(w["mix"]) != {"read", "write", "cpu"} or any(x < 0 for x in w["mix"].values()):
        raise ConfigError("Tỷ lệ workload không hợp lệ")
    if abs(sum(w["mix"].values()) - 1) > 1e-9:
        raise ConfigError("Tổng tỷ lệ endpoint phải bằng 1")
    if not t["read_ids"] or len(set(t["read_ids"])) != len(t["read_ids"]):
        raise ConfigError("read_ids phải có sẵn, duy nhất")
    if w["max_vus"] < w["preallocated_vus"] or w["preallocated_vus"] < 1:
        raise ConfigError("Cấu hình VU không hợp lệ")
    if e["repeats"] < 1 or e["bootstrap_resamples"] < 100:
        raise ConfigError("repeats/bootstrap không hợp lệ")
    if e["comparison_mode"] not in {"controlled", "deployment"}:
        raise ConfigError("comparison_mode phải là controlled hoặc deployment")
    for key in ("baseline_rps", "peak_rps", "baseline_seconds", "ramp_seconds", "hold_seconds", "recovery_seconds"):
        value = w["burst"][key]
        if not math.isfinite(value) or value <= 0:
            raise ConfigError(f"burst.{key} phải hữu hạn, > 0")
    if w["burst"]["peak_rps"] < w["burst"]["baseline_rps"]:
        raise ConfigError("burst.peak_rps phải >= baseline_rps")
    for key in ("budget_usd", "max_requests", "max_rps"):
        if not math.isfinite(e["safety"][key]) or e["safety"][key] <= 0:
            raise ConfigError(f"safety.{key} phải hữu hạn, > 0")
    if t["timeout_seconds"] <= 0 or e["cooldown_seconds"] < 0:
        raise ConfigError("Thời lượng không hợp lệ")
    for key in ("warmup_seconds", "measurement_seconds"):
        if w["steady"][key] <= 0:
            raise ConfigError(f"steady.{key} phải > 0")
    if any(v <= 0 for v in w["steady"]["rates"].values()):
        raise ConfigError("RPS phải > 0")
    if w["idle"]["idle_seconds"] < 0 or w["idle"]["warm_requests"] < 1:
        raise ConfigError("idle không hợp lệ")
    for endpoint in t["endpoints"].values():
        if endpoint["method"] not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            raise ConfigError("HTTP method không hỗ trợ")
        if not endpoint["path"].startswith("/") or not endpoint["response_schema"]:
            raise ConfigError("Endpoint cần path và response_schema")


def target_config(c: dict, model: str) -> dict:
    result = copy.deepcopy(c["targets"]["targets"][model])
    result["url"] = os.environ.get(result["url_env"], "").rstrip("/")
    if result["url"]:
        parsed = urlsplit(result["url"])
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ConfigError("Target URL phải là HTTP(S), không chứa credential/query/fragment; đặt auth trong env token")
    result["project"] = os.environ.get(result["project_env"], "")
    return result


def request_headers(c: dict, model: str) -> dict[str, str]:
    headers = dict(c["targets"].get("headers", {}))
    token = os.environ.get(c["targets"]["targets"][model]["token_env"], "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if any(s in k.lower() for s in ("authorization", "token", "secret", "password", "api_key")) else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value
