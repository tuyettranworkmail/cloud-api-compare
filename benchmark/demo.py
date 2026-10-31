"""Deterministic synthetic fixtures. Never called from REAL runner or ingestion."""
from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from benchmark.io import DEMO_LABEL, write_json
from benchmark.runner import plan_experiments


def generate_demo(c: dict, output=Path("demo_data"), seed=20261031, repeats=5) -> dict:
    config = copy.deepcopy(c)
    config["workloads"]["steady"].update(warmup_seconds=3, measurement_seconds=18)
    config["workloads"]["burst"].update(warmup_seconds=3, baseline_seconds=6, ramp_seconds=1, hold_seconds=6, recovery_seconds=6)
    config["experiments"]["experiment_id"] = "simulated"
    config["experiments"]["seed"] = seed
    rng = np.random.default_rng(seed)
    plans = plan_experiments(config, repeats=repeats)
    origin = datetime(2026, 10, 1, tzinfo=timezone.utc)
    request_total = 0
    for index, params in enumerate(plans):
        directory = output / "raw" / params["run_id"]
        directory.mkdir(parents=True, exist_ok=True)
        model, scenario = params["model"], params["scenario"]
        measurement_start = origin + timedelta(hours=index)
        measurement_ms = measurement_start.timestamp() * 1000
        run_effect = rng.lognormal(0, .10)
        rows, logs = [], []
        # Simulated arrival schedule includes a separately tagged warm-up.
        arrivals = []
        if scenario == "steady":
            arrivals = [(i / params["rate"] - params["warmup_seconds"], "warmup") for i in range(params["rate"] * params["warmup_seconds"])]
            arrivals += [(i / params["rate"], "measurement") for i in range(params["rate"] * params["measurement_seconds"])]
        elif scenario == "burst":
            for second in range(-params["warmup_seconds"], params["measurement_seconds"]):
                rate = params["baseline_rps"] if second < params["baseline_seconds"] or second >= params["baseline_seconds"] + params["ramp_seconds"] + params["hold_seconds"] else params["peak_rps"]
                arrivals.extend((second + i / rate, "warmup" if second < 0 else "measurement") for i in range(rate))
        else:
            arrivals = [(float(i), "first_after_idle" if i == 0 else "measurement") for i in range(params["warm_requests"] + 1)]
        with (directory / "k6.jsonl").open("w", encoding="utf-8") as stream:
            for i, (second, phase) in enumerate(arrivals):
                endpoint = str(rng.choice(["read", "write", "cpu"], p=[.7, .2, .1]))
                base = {"read": 35, "write": 52, "cpu": 110}[endpoint]
                latency = float(rng.lognormal(np.log(base * run_effect), .38))
                if scenario == "burst" and 6 <= second < 14:
                    latency *= 2.0 if model == "iaas" else 1.4
                if rng.random() < .003:
                    latency *= 15
                classification = "unknown" if rng.random() < .06 else "confirmed_warm"
                cold = scenario == "idle" and i == 0 and model != "iaas" and params["repeat"] != 2
                if cold:
                    latency += float(rng.uniform(200, 1200))
                    classification = "application_first_request"
                elif scenario == "idle" and i == 0 and model != "iaas":
                    classification = "unknown"
                draw = rng.random()
                status = 0 if draw < .002 else 503 if draw < .012 else 201 if endpoint == "write" else 200
                success = status > 0 and status < 400 and draw >= .014
                request_id = params["run_id"] + f"-{i}"
                handler = latency * .72 if rng.random() > .04 else None
                timestamp = (measurement_start + timedelta(seconds=second, milliseconds=latency)).isoformat()
                tags = {"request_id": request_id, "run_id": params["run_id"], "deployment_model": model, "endpoint": endpoint, "scenario_name": scenario, "load_level": params["load_level"], "phase": phase, "data_mode": "DEMO", "classification": classification, "instance_id": f"sim-{model}-{index}-1", "status": str(status), "success": str(success).lower(), "handler_ms": str(handler) if handler is not None else "", "wall_ms": str(latency + 2), "error_code": "1050" if status == 0 else "", "scenario_start_ms": str(measurement_ms - (params["warmup_seconds"] * 1000 if phase == "warmup" else 0))}
                point = {"type": "Point", "metric": "request_sample_ms", "data": {"time": timestamp, "value": latency, "tags": tags}}
                stream.write(json.dumps(point, separators=(",", ":")) + "\n")
                rows.append(latency)
                if cold:
                    logs.append({"timestamp": timestamp, "request_id": request_id, "instance_id": tags["instance_id"], "platform_startup_confirmed": True, "cold_start_scope": "SIMULATED_PLATFORM_EVIDENCE"})
            dropped = 3 if model == "iaas" and scenario == "steady" and params["load_level"] == "high" and params["repeat"] == 1 else 0
            for metric, value in {"http_req_duration": float(np.mean(rows)), "http_req_waiting": float(np.mean(rows)) * .95, "http_req_blocked": 1, "http_req_connecting": .5, "http_req_tls_handshaking": .3, "http_reqs": len(rows), "http_req_failed": .012, "iterations": len(rows), "iteration_duration": float(np.mean(rows)), "dropped_iterations": dropped, "vus": 20, "vus_max": 200, "checks": 1}.items():
                stream.write(json.dumps({"type": "Point", "metric": metric, "data": {"time": measurement_start.isoformat(), "value": value, "tags": {"scenario": "measurement"}}}) + "\n")
        meta = {**params, "mix": config["workloads"]["mix"], "data_mode": "DEMO", "label": DEMO_LABEL, "status": "COMPLETE", "attempt": 1, "measurement_started_at": measurement_start.isoformat(), "k6_started_at": (measurement_start - timedelta(seconds=params["warmup_seconds"])).isoformat(), "started_at": measurement_start.isoformat(), "seed": seed, "simulation": {"purpose": "pipeline validation only", "cloud_measured": False, "generator": "seeded lognormal latency with errors and outliers", "fairness": "synthetic arrivals are illustrative; not evidence of GCP differences"}}
        write_json(directory / "metadata.json", meta)
        write_json(directory / "summary.json", {"data_mode": "DEMO", "label": DEMO_LABEL, "metrics": {"request_sample_ms": {"values": {"count": len(rows), "avg": float(np.mean(rows)), "p(95)": float(np.quantile(rows, .95))}}}})
        if logs:
            (directory / "application.jsonl").write_text("\n".join(json.dumps(log) for log in logs) + "\n", encoding="utf-8")
        monitoring = {"data_mode": "DEMO", "label": DEMO_LABEL, "sampling_seconds": 60, "visibility_delay_seconds": 120, "series": []}
        # Short demo burst: only a coarse post-burst sample. Exact reaction cannot be inferred.
        for alias, unit in (("instance_count", "1"), ("cpu", "1"), ("memory", "1"), ("startup_latency", "ms"), ("billable_instance_time", "s")):
            if model == "iaas" and alias in {"instance_count", "startup_latency", "billable_instance_time"}:
                continue
            if model == "faas" and params["repeat"] == 3 and alias == "memory":
                continue
            points = []
            for second in [-60, 0, 60, 120]:
                value = (2 if scenario == "burst" and second == 60 else 1) if alias == "instance_count" else float(rng.uniform(.1, .8)) if alias in {"cpu", "memory"} else float(rng.uniform(100, 500)) if alias == "startup_latency" else 12
                key = "int64_value" if alias == "instance_count" else "double_value"
                points.append({"interval": {"end_time": (measurement_start + timedelta(seconds=second)).isoformat()}, "value": {key: str(value) if key == "int64_value" else value}})
            monitoring["series"].append({"alias": alias, "unit": unit, "metric": {"labels": {}}, "resource": {"labels": {}}, "points": points})
        write_json(directory / "monitoring.json", monitoring)
        request_total += len(rows)
    write_json(output / "manifest.json", {"data_mode": "DEMO", "label": DEMO_LABEL, "seed": seed, "runs": len(plans), "requests": request_total, "real_cloud_measurements": False})
    (output / "README.md").write_text(f"# {DEMO_LABEL}\n\nDữ liệu sinh bằng benchmark.demo, seed={seed}. Không dùng để kết luận GCP.\n", encoding="utf-8")
    return {"runs": len(plans), "requests": request_total, "seed": seed, "label": DEMO_LABEL}
