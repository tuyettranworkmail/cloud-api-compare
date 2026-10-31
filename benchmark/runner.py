"""Sequential, resumable experiment runner with fail-closed spending bounds."""
from __future__ import annotations

import copy
import importlib.metadata
import math
import os
import platform
import random
import shutil
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import psutil

from benchmark.collectors.gcp import collect_logs, collect_metrics, resource_snapshot
from benchmark.config import ConfigError, redact, request_headers, target_config
from benchmark.io import file_hash, fingerprint, read_json, utcnow, write_json
from benchmark.validators import validate_contracts

ROOT = Path(__file__).resolve().parents[1]


def k6_binary() -> str:
    binary = os.environ.get("K6_BIN", "k6")
    local = ROOT / ".tools" / ("k6.exe" if os.name == "nt" else "k6")
    found = shutil.which(binary) or (str(local) if binary == "k6" and local.exists() else None)
    if not found:
        raise ConfigError("Không tìm thấy k6; xem README hoặc chạy scripts/install_k6.py")
    return found


def scenario_parameters(c: dict, scenario: str, level: str, endpoint: str | None) -> dict:
    w = c["workloads"]
    result = {**copy.deepcopy(w.get(scenario, {})), "scenario": scenario, "load_level": level, "endpoint": endpoint, "mix": w["mix"], "preallocated_vus": w["preallocated_vus"], "max_vus": w["max_vus"], "graceful_stop_seconds": w["graceful_stop_seconds"]}
    if scenario == "steady":
        result["rate"] = w["steady"]["rates"][level]
        result["offered_requests"] = result["rate"] * (result["warmup_seconds"] + result["measurement_seconds"])
        result["max_rps"] = result["rate"]
    elif scenario == "burst":
        result["rate"] = result["baseline_rps"]
        result["measurement_seconds"] = result["baseline_seconds"] + 2 * result["ramp_seconds"] + result["hold_seconds"] + result["recovery_seconds"]
        result["offered_requests"] = result["baseline_rps"] * (result["warmup_seconds"] + result["baseline_seconds"] + result["recovery_seconds"]) + result["ramp_seconds"] * (result["baseline_rps"] + result["peak_rps"]) + result["hold_seconds"] * result["peak_rps"]
        result["max_rps"] = result["peak_rps"]
    elif scenario == "idle":
        result.update(rate=1, max_rps=1, warmup_seconds=0)
        result["measurement_seconds"] = (result["warm_requests"] + 1) * (c["targets"]["timeout_seconds"] + result["interval_seconds"])
        result["offered_requests"] = result["warm_requests"] + 1
    else:
        raise ConfigError("Scenario phải là steady/burst/idle")
    # Worst-case request count also budgets one full smoke validation of all targets.
    result["request_bound"] = math.ceil(result["offered_requests"]) + 3 * (len(c["targets"]["read_ids"]) + 3) + 4
    result["wall_bound_seconds"] = result["warmup_seconds"] + result["measurement_seconds"] + result["graceful_stop_seconds"] + result.get("idle_seconds", 0) + c["experiments"]["cooldown_seconds"] + c["experiments"]["monitoring"]["settle_seconds"] + 300
    return result


def plan_experiments(c: dict, scenarios=None, models=None, levels=None, repeats=None, endpoint=None) -> list[dict]:
    scenarios = scenarios or ["steady", "burst", "idle"]
    models = models or ["iaas", "paas", "faas"]
    levels = levels or list(c["workloads"]["steady"]["rates"])
    repeats = repeats if repeats is not None else c["experiments"]["repeats"]
    if repeats < 1 or repeats > 1000:
        raise ConfigError("repeats phải từ 1 đến 1000")
    rng = random.Random(c["experiments"]["seed"])
    runs = []
    for repeat in range(repeats):
        for scenario in scenarios:
            for level in levels if scenario == "steady" else ["burst" if scenario == "burst" else "idle"]:
                order = list(models)
                rng.shuffle(order)
                for model in order:
                    params = scenario_parameters(c, scenario, level, endpoint)
                    params.update(model=model, repeat=repeat + 1, seed=c["experiments"]["seed"] + repeat)
                    params["run_id"] = f'{c["experiments"]["experiment_id"]}-{model}-{scenario}-{level}-{endpoint or "mixed"}-r{repeat + 1:02}'
                    runs.append(params)
    return runs


def spending_bound(c: dict, params: dict) -> float:
    safety = c["experiments"]["safety"]
    request_price = safety["verified_upper_usd_per_request"]
    hour_price = safety["verified_upper_usd_per_hour"]
    if request_price is None or hour_price is None or request_price < 0 or hour_price <= 0:
        raise ConfigError("Thiếu trần chi phí đã kiểm chứng/request và /hour; không được chạy REAL")
    return params["request_bound"] * request_price + params["wall_bound_seconds"] / 3600 * hour_price


@contextmanager
def experiment_lock(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "runner.lock"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise ConfigError("Runner đang chạy hoặc bị gián đoạn. Kiểm tra PID trong runner.lock trước khi xóa lock thủ công.") from error
    try:
        os.write(descriptor, str(os.getpid()).encode())
        os.close(descriptor)
        yield
    finally:
        path.unlink(missing_ok=True)


def generator_preflight(c: dict) -> dict:
    load = c["experiments"]["load_generator"]
    cpu, memory = psutil.cpu_percent(interval=1), psutil.virtual_memory().percent
    result = {"cpu_percent": cpu, "memory_percent": memory, "logical_cpu_count": psutil.cpu_count(), "total_memory_gib": psutil.virtual_memory().total / 2**30, "python": sys.version, "platform": platform.platform(), "configured_region": load["region"]}
    if load["region"] != c["targets"]["region"] or not load["independent_vm"]:
        raise ConfigError("Máy tạo tải cần VM riêng trong cùng region")
    if cpu > load["maximum_cpu_percent"] or memory > load["maximum_memory_percent"]:
        raise ConfigError("Máy tạo tải đang quá bận")
    if load["require_metadata_server"]:
        response = httpx.get("http://metadata.google.internal/computeMetadata/v1/instance/zone", headers={"Metadata-Flavor": "Google"}, timeout=3, trust_env=False)
        response.raise_for_status()
        zone = response.text.split("/")[-1]
        if not zone.startswith(load["region"] + "-"):
            raise ConfigError("Region thực tế của VM tạo tải không đúng")
        result["verified_zone"] = zone
        identity = httpx.get("http://metadata.google.internal/computeMetadata/v1/instance/id", headers={"Metadata-Flavor": "Google"}, timeout=3, trust_env=False)
        identity.raise_for_status()
        result["verified_instance_id"] = identity.text.strip()
        if result["verified_instance_id"] == c["targets"]["targets"]["iaas"]["instance_id"]:
            raise ConfigError("Máy tạo tải không được dùng chung VM với IaaS API")
    return result


def _wait(seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        time.sleep(min(30, deadline - time.monotonic()))


def execute_plan(c: dict, plans: list[dict], output: Path = Path("results"), *, dry_run=False, resume=False) -> dict:
    output = output.resolve()
    if dry_run:
        policies = []
        try:
            total = sum(spending_bound(c, p) for p in plans)
        except ConfigError as error:
            total = None
            policies.append(str(error))
        return {"dry_run": True, "runs": plans, "request_bound": sum(p["request_bound"] for p in plans), "upper_cost_usd": total, "budget_usd": c["experiments"]["safety"]["budget_usd"], "policy_notes": policies, "cloud_contacted": False}
    safety = c["experiments"]["safety"]
    if not safety["quota_verified"] or not safety["allow_benchmark_writes"]:
        raise ConfigError("Phải xác minh quota và cho phép ghi benchmark trong cấu hình")
    binary = k6_binary()
    generator = generator_preflight(c)
    config_hash = fingerprint({"config": c, "targets": {m: target_config(c, m) for m in c["targets"]["targets"]}})
    with experiment_lock(output):
        ledger_path = output / "budget_ledger.json"
        ledger = read_json(ledger_path) if ledger_path.exists() else {"reserved_upper_usd": 0.0, "reserved_requests": 0, "attempts": []}
        pending = []
        for params in plans:
            parent = output / "raw" / params["run_id"]
            previous = sorted(parent.glob("attempt-*/metadata.json"))
            if resume and previous:
                meta = read_json(previous[-1])
                if meta.get("config_hash") == config_hash and meta["status"] == "COMPLETE":
                    continue
            params = dict(params)
            params["attempt"] = len(previous) + 1
            cost = spending_bound(c, params)
            if params["max_rps"] > safety["max_rps"]:
                raise ConfigError("RPS kế hoạch vượt trần cấu hình")
            params["cost_bound_usd"] = cost
            pending.append(params)
        if ledger["reserved_upper_usd"] + sum(p["cost_bound_usd"] for p in pending) > safety["budget_usd"]:
            raise ConfigError("Ngân sách không đủ cho toàn bộ kế hoạch; tăng ngân sách có chủ đích hoặc giảm kế hoạch")
        if ledger["reserved_requests"] + sum(p["request_bound"] for p in pending) > safety["max_requests"]:
            raise ConfigError("Số request tối đa vượt trần; giảm kế hoạch hoặc cập nhật trần có chủ đích")
        statuses = []
        for params in pending:
            directory = output / "raw" / params["run_id"] / f'attempt-{params["attempt"]:03}'
            directory.mkdir(parents=True, exist_ok=False)
            # Reserve BEFORE any API smoke writes. Failed/interrupted attempts retain reservation.
            ledger["reserved_upper_usd"] += params["cost_bound_usd"]
            ledger["reserved_requests"] += params["request_bound"]
            ledger["attempts"].append({"run_id": params["run_id"], "attempt": params["attempt"], "upper_cost_usd": params["cost_bound_usd"], "reserved_at": utcnow()})
            write_json(ledger_path, ledger)
            meta = {**params, "data_mode": "REAL", "config_hash": config_hash, "status": "RUNNING", "started_at": utcnow(), "generator": generator, "config": redact(c), "warnings": [], "files": {}}
            write_json(directory / "metadata.json", meta)
            try:
                validation = validate_contracts(c, allow_writes=True)
                write_json(directory / "compatibility.json", validation)
                if not validation["passed"]:
                    raise ConfigError("Compatibility thất bại; xem compatibility.json")
                if safety["require_resource_snapshot"]:
                    from benchmark.fairness import fairness_report
                    snapshots = {model: resource_snapshot(c, model) for model in ("iaas", "paas", "faas")}
                    meta["resource_snapshot"] = snapshots[params["model"]]
                    meta["all_resource_snapshots"] = snapshots
                    fairness = fairness_report(c, snapshots)
                    write_json(directory / "fairness.json", fairness)
                    if c["experiments"]["comparison_mode"] == "controlled" and not fairness["controlled_limits_verified"]:
                        raise ConfigError("Controlled resource verification thất bại; xem fairness.json hoặc chọn deployment mode để nghiên cứu cấu hình thực tế")
                    if params["model"] == "iaas":
                        configured_id = target_config(c, "iaas")["instance_id"]
                        if configured_id != meta["resource_snapshot"]["instance_id"]:
                            raise ConfigError("instance_id cấu hình không khớp VM thực")
                meta["versions"] = {name: importlib.metadata.version(name) for name in ("numpy", "pandas", "scipy", "httpx", "google-cloud-monitoring")}
                meta["k6_version"] = subprocess.check_output([binary, "version"], text=True).strip()
                sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT)
                meta["git_sha"] = sha.stdout.strip() if sha.returncode == 0 else None
                if meta["git_sha"] is None:
                    meta["warnings"].append("Chưa có Git commit; lưu source hashes thay thế")
                meta["source_hashes"] = {str(path.relative_to(ROOT)): file_hash(path) for folder in ("benchmark", "k6", "configs") for path in (ROOT / folder).rglob("*") if path.is_file() and path.suffix in {".py", ".js", ".yaml"}}
                if params["scenario"] == "idle":
                    meta["idle_start"] = utcnow()
                    deadline = time.monotonic() + params["idle_seconds"]
                    idle_samples = []
                    while time.monotonic() < deadline:
                        _wait(min(c["experiments"]["monitoring"]["poll_seconds"], max(0, deadline - time.monotonic())))
                        if c["experiments"]["monitoring"]["enabled"]:
                            try:
                                sample = collect_metrics(c, params["model"], meta["idle_start"], utcnow(), directory / "idle_monitoring.json")
                                idle_samples.append({"at": utcnow(), "metric_status": sample["metric_status"]})
                            except Exception as error:
                                meta["warnings"].append(f"Idle monitoring: {type(error).__name__}")
                    meta["idle_end"] = utcnow()
                    meta["idle_samples"] = idle_samples
                    meta["cold_start_confirmation"] = "UNKNOWN_UNLESS_PLATFORM_EVIDENCE"
                run_config = {**params, "url": target_config(c, params["model"])["url"], "headers": request_headers(c, params["model"]), "endpoints": c["targets"]["endpoints"], "read_ids": c["targets"]["read_ids"], "timeout_seconds": c["targets"]["timeout_seconds"], "data_mode": "REAL", "summary_path": str(directory / "summary.json")}
                # File contains short-lived auth only while k6 runs; removed even on exceptions.
                private_path = directory / "private_runtime_config.json"
                write_json(private_path, run_config)
                script = "idle_request.js" if params["scenario"] == "idle" else params["scenario"] + ".js"
                command = [binary, "run", "--out", f'json={directory / "k6.jsonl"}', str(ROOT / "k6" / script)]
                environment = {**os.environ, "BENCH_RUN_CONFIG": str(private_path)}
                meta["k6_started_at"] = utcnow()
                monitor_stop = threading.Event()
                generator_samples = []

                def sample_generator():
                    while not monitor_stop.wait(1):
                        generator_samples.append({"timestamp": utcnow(), "cpu_percent": psutil.cpu_percent(), "memory_percent": psutil.virtual_memory().percent})

                watcher = threading.Thread(target=sample_generator, daemon=True)
                watcher.start()
                try:
                    with (directory / "k6.stdout.log").open("w", encoding="utf-8") as stdout, (directory / "k6.stderr.log").open("w", encoding="utf-8") as stderr:
                        completed = subprocess.run(command, env=environment, stdout=stdout, stderr=stderr, timeout=params["wall_bound_seconds"])
                finally:
                    monitor_stop.set()
                    watcher.join(timeout=2)
                    private_path.unlink(missing_ok=True)
                meta["k6_ended_at"] = utcnow()
                meta["exit_code"] = completed.returncode
                write_json(directory / "generator.json", generator_samples)
                busy = any(p["cpu_percent"] > c["experiments"]["load_generator"]["maximum_cpu_percent"] or p["memory_percent"] > c["experiments"]["load_generator"]["maximum_memory_percent"] for p in generator_samples)
                if busy:
                    meta["warnings"].append("Load generator saturation observed; results may be invalid")
                if completed.returncode != 0:
                    raise RuntimeError(f"k6 exit={completed.returncode}; dữ liệu một phần được giữ nguyên")
                if not (directory / "k6.jsonl").exists() or not (directory / "summary.json").exists():
                    raise RuntimeError("k6 không tạo đủ raw và summary artifacts")
                summary_metrics = read_json(directory / "summary.json").get("metrics", {})
                dropped = summary_metrics.get("dropped_iterations", {}).get("values", {}).get("count", 0)
                meta["dropped_iterations"] = dropped
                if dropped:
                    meta["warnings"].append("Dropped iterations observed; offered workload was not fully generated")
                if c["experiments"]["monitoring"]["enabled"]:
                    _wait(c["experiments"]["monitoring"]["settle_seconds"])
                    try:
                        start = (datetime.fromisoformat(meta["k6_started_at"]) - timedelta(seconds=180)).isoformat()
                        monitoring = collect_metrics(c, params["model"], start, meta["k6_ended_at"], directory / "monitoring.json")
                        meta["monitoring_status"] = monitoring["metric_status"]
                        if any(v != "OK" for v in monitoring["metric_status"].values()):
                            meta["warnings"].append("Monitoring có metric thiếu/lỗi; không suy diễn giá trị 0")
                        if c["experiments"]["monitoring"]["logs_enabled"]:
                            meta["logs_status"] = collect_logs(c, params["model"], meta["k6_started_at"], meta["k6_ended_at"], directory / "application.jsonl")
                    except Exception as error:
                        meta["warnings"].append(f"Monitoring unavailable: {type(error).__name__}")
                meta["status"] = "INVALID_GENERATOR" if busy else "INVALID_DROPPED_ITERATIONS" if dropped else "COMPLETE"
            except (Exception, KeyboardInterrupt) as error:
                meta["status"] = "INTERRUPTED" if isinstance(error, KeyboardInterrupt) else "FAILED"
                meta["failure"] = type(error).__name__
                # Controlled messages only: arbitrary network exceptions can include credentials.
                if isinstance(error, (ConfigError, RuntimeError)):
                    meta["failure_detail"] = str(error)
            finally:
                (directory / "private_runtime_config.json").unlink(missing_ok=True)
                meta["ended_at"] = utcnow()
                meta["files"] = {p.name: file_hash(p) for p in directory.iterdir() if p.is_file() and p.name != "metadata.json"}
                write_json(directory / "metadata.json", meta)
            statuses.append({"run_id": params["run_id"], "attempt": params["attempt"], "status": meta["status"]})
            print(f'{params["run_id"]}: {meta["status"]}', flush=True)
            if meta["status"] in {"FAILED", "INTERRUPTED"}:
                break
            _wait(c["experiments"]["cooldown_seconds"])
        summary = {"timestamp": utcnow(), "runs": statuses, "planned": len(plans), "skipped_resume": len(plans) - len(pending), "remaining_not_started": len(pending) - len(statuses), "reserved_upper_usd": ledger["reserved_upper_usd"]}
        write_json(output / "execution_status.json", summary)
        return summary
