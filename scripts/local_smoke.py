"""Exercise current k6 against three local API fixtures, never against cloud URLs."""
from __future__ import annotations

import copy
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

from benchmark.config import load_config
from benchmark.io import utcnow, write_json
from benchmark.parsers.k6 import clean_requests, parse_k6
from benchmark.runner import k6_binary, scenario_parameters
from benchmark.validators import validate_contracts


def main() -> int:
    config = copy.deepcopy(load_config())
    config["workloads"]["steady"].update(warmup_seconds=1, measurement_seconds=2, rates={"low": 2, "medium": 3, "high": 5})
    config["workloads"]["burst"].update(warmup_seconds=1, baseline_rps=2, peak_rps=5, baseline_seconds=2, ramp_seconds=1, hold_seconds=2, recovery_seconds=2)
    config["workloads"]["idle"].update(idle_seconds=0, warm_requests=3, interval_seconds=.05)
    config["workloads"].update(preallocated_vus=2, max_vus=10, graceful_stop_seconds=2)
    config["targets"]["timeout_seconds"] = 2
    root = Path("results/local_smoke")
    if (root / "summary.json").exists():
        # Preserve old verification artifacts; a new timestamp directory is reviewable.
        root = root / utcnow().replace(":", "-")
    root.mkdir(parents=True, exist_ok=True)
    processes, files = [], []
    try:
        for model in ("iaas", "paas", "faas"):
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            url = f"http://127.0.0.1:{port}"
            os.environ[model.upper() + "_URL"] = url
            log = (root / f"{model}.server.log").open("w", encoding="utf-8")
            files.append(log)
            process = subprocess.Popen([sys.executable, "-m", "uvicorn", "examples.mock_api:create_app", "--factory", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"], env={**os.environ, "MOCK_MODEL": model}, stdout=log, stderr=log)
            processes.append(process)
            for attempt in range(100):
                try:
                    if httpx.get(url + "/openapi.json", timeout=.5).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(.1)
            else:
                raise RuntimeError("Local server failed to start")
        report = validate_contracts(config, allow_writes=True)
        write_json(root / "compatibility.json", report)
        if not report["passed"]:
            raise RuntimeError("Local compatibility failed")
        binary = k6_binary()
        results = []
        jobs = [(model, scenario, None) for model in ("iaas", "paas", "faas") for scenario in ("steady", "burst", "idle")]
        jobs += [("iaas", "steady", endpoint) for endpoint in ("read", "write", "cpu")]
        for number, (model, scenario, endpoint) in enumerate(jobs):
            params = scenario_parameters(config, scenario, "low", endpoint)
            run_id = f"local-{model}-{scenario}-{endpoint or 'mixed'}-{number}"
            directory = root / "raw" / run_id
            directory.mkdir(parents=True, exist_ok=True)
            meta = {**params, "run_id": run_id, "model": model, "data_mode": "LOCAL_TEST", "label": "LOCAL TEST — NOT REAL CLOUD MEASUREMENTS", "repeat": 1, "seed": 42, "status": "COMPLETE", "k6_started_at": utcnow()}
            run_config = {**meta, "url": os.environ[model.upper() + "_URL"], "headers": {}, "timeout_seconds": 2, "endpoints": config["targets"]["endpoints"], "read_ids": config["targets"]["read_ids"], "summary_path": str((directory / "summary.json").resolve())}
            write_json(directory / "runtime.json", run_config)
            script = f"{endpoint}_endpoint.js" if endpoint else "idle_request.js" if scenario == "idle" else scenario + ".js"
            result = subprocess.run([binary, "run", "--out", "json=" + str((directory / "k6.jsonl").resolve()), "--out", "csv=" + str((directory / "k6.csv").resolve()), str(Path("k6") / script)], env={**os.environ, "BENCH_RUN_CONFIG": str((directory / "runtime.json").resolve())}, capture_output=True, text=True, encoding="utf-8", timeout=45)
            (directory / "stdout.log").write_text(result.stdout, encoding="utf-8")
            (directory / "stderr.log").write_text(result.stderr, encoding="utf-8")
            meta["k6_ended_at"] = utcnow()
            if result.returncode:
                meta["status"] = "FAILED"
            write_json(directory / "metadata.json", meta)
            if result.returncode:
                raise RuntimeError(f"{script} failed; see {directory / 'stderr.log'}")
            frame, metrics, parsing = parse_k6(directory / "k6.jsonl", meta)
            cleaned, quality = clean_requests(frame)
            if cleaned.empty or not cleaned["success"].all():
                raise RuntimeError("Local k6 did not produce valid successful request samples")
            csv_frame, _, _ = parse_k6(directory / "k6.csv", meta)
            csv_clean, _ = clean_requests(csv_frame)
            if len(csv_clean) != len(cleaned) or set(csv_clean["request_id"]) != set(cleaned["request_id"]):
                raise RuntimeError("Native CSV and JSONL request identities do not match")
            results.append({"model": model, "script": script, "request_count": len(cleaned), "exit_code": result.returncode, "raw_metrics": sorted(set(metrics["metric"])), "parse_issues": parsing, "quality": quality})
            print(model, script, len(cleaned), "PASS", flush=True)
        write_json(root / "summary.json", {"label": "LOCAL TEST — NOT REAL CLOUD MEASUREMENTS", "k6_version": subprocess.check_output([binary, "version"], text=True).strip(), "verified_at": utcnow(), "jobs": results, "all_passed": True})
        print(json.dumps({"all_passed": True, "jobs": len(results), "artifacts": str(root)}))
        return 0
    finally:
        for process in processes:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for file in files:
            file.close()


if __name__ == "__main__":
    raise SystemExit(main())
