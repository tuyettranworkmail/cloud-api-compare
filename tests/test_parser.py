import json

import numpy as np
import pandas as pd
import pytest

from benchmark.parsers.k6 import clean_requests, join_application_logs, parse_k6


def point(**tags):
    return {"type": "Point", "metric": "request_sample_ms", "data": {"time": "2026-10-01T00:00:00Z", "value": 10, "tags": {"request_id": "r-1", "status": "200", "success": "true", "phase": "measurement", "classification": "application_first_request", **tags}}}


def test_raw_parse_and_missing_handler(tmp_path):
    path = tmp_path / "k6.jsonl"
    path.write_text(json.dumps(point()) + "\n{bad json\n", encoding="utf-8")
    before = path.read_bytes()
    frame, metrics, report = parse_k6(path, {"run_id": "r", "model": "paas", "scenario": "idle", "data_mode": "REAL"})
    cleaned, quality = clean_requests(frame)
    assert len(cleaned) == 1
    assert np.isnan(cleaned.iloc[0]["handler_ms"])
    assert cleaned.iloc[0]["classification"] == "application_first_request"
    assert report["parse_errors"][0]["reason"] == "MALFORMED_JSON"
    assert path.read_bytes() == before


def test_mode_required(tmp_path):
    with pytest.raises(ValueError, match="data_mode"):
        parse_k6(tmp_path / "irrelevant", {"run_id": "r"})


def test_duplicate_exact_vs_conflicting(tmp_path):
    path = tmp_path / "k6.jsonl"
    path.write_text("\n".join(json.dumps(x) for x in [point(), point(), point(request_id="r-2"), point(request_id="r-2", status="500")]), encoding="utf-8")
    frame, _, _ = parse_k6(path, {"run_id": "r", "model": "paas", "scenario": "idle", "data_mode": "DEMO"})
    result, report = clean_requests(frame)
    assert len(result) == 1
    assert report["duplicates"] == 1
    assert report["conflicting_request_keys"] == 1


def test_outlier_retained_and_bad_latency_quarantined():
    base = {"timestamp": "2026-01-01T00:00:00Z", "run_id": "r", "data_mode": "REAL", "endpoint": "read", "status": 200, "success": True, "classification": "unknown", "error_code": "", "phase": "measurement"}
    frame = pd.DataFrame([{**base, "request_id": str(i), "latency_ms": value} for i, value in enumerate([10] * 10 + [10000, -1])])
    result, report = clean_requests(frame)
    assert len(result) == 11
    assert result["latency_ms"].max() == 10000
    assert result["outlier"].sum() == 1
    assert report["invalid_rows"] == 1


def test_process_first_not_promoted_without_platform_evidence(tmp_path):
    path = tmp_path / "logs.jsonl"
    path.write_text(json.dumps({"request_id": "r-1", "cold_start": True}) + "\n", encoding="utf-8")
    result, _ = join_application_logs(pd.DataFrame([{"request_id": "r-1", "classification": "application_first_request"}]), path)
    assert result.iloc[0]["classification"] == "application_first_request"


def test_platform_evidence_promotes_only_first_request(tmp_path):
    path = tmp_path / "logs.jsonl"
    path.write_text(json.dumps({"request_id": "r-1", "platform_startup_confirmed": True}) + "\n", encoding="utf-8")
    result, _ = join_application_logs(pd.DataFrame([{"request_id": "r-1", "classification": "application_first_request"}]), path)
    assert result.iloc[0]["classification"] == "confirmed_cold"
