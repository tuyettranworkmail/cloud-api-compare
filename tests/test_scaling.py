import numpy as np
import pandas as pd

from benchmark.scaling.analysis import analyze_scaling, cold_warm_analysis, monitoring_frame
from benchmark.io import write_json


def test_iaas_fixed_vm_is_na_not_zero():
    result = analyze_scaling(pd.DataFrame(), {"model": "iaas", "run_id": "r", "scenario": "burst", "data_mode": "REAL"})
    assert result["status"] == "NOT_APPLICABLE_FIXED_VM"
    assert np.isnan(result["scale_out_seconds"])


def test_scale_out_interval_censored_by_samples():
    meta = {"model": "paas", "run_id": "r", "scenario": "burst", "data_mode": "REAL", "measurement_started_at": "2026-01-01T00:00:00Z", "baseline_seconds": 10, "ramp_seconds": 2, "hold_seconds": 60}
    frame = pd.DataFrame({"metric": ["instance_count"] * 3, "timestamp": pd.to_datetime(["2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z", "2026-01-01T00:02:00Z"], utc=True), "value": [1, 3, 1], "sampling_seconds": [60] * 3})
    result = analyze_scaling(frame, meta)
    assert result["scale_out_lower_seconds"] == 0
    assert result["scale_out_upper_seconds"] == 50
    assert result["recovery_seconds"] == 46


def test_no_monitoring_not_zero():
    result = analyze_scaling(pd.DataFrame(), {"model": "faas", "run_id": "r", "scenario": "burst", "data_mode": "REAL"})
    assert result["status"] == "INSUFFICIENT_DATA"


def test_instance_count_sums_states_and_revisions(tmp_path):
    path = tmp_path / "monitoring.json"
    raw = {"data_mode": "REAL", "series": [{"alias": "instance_count", "metric": {"labels": {"state": state}}, "points": [{"interval": {"end_time": "2026-01-01T00:00:00Z"}, "value": {"int64_value": value}}]} for state, value in [("active", "2"), ("idle", "3")]]}
    write_json(path, raw)
    frame = monitoring_frame(path, {"run_id": "r", "model": "paas", "data_mode": "REAL"})
    assert frame.iloc[0]["value"] == 5


def test_no_confirmed_cold_means_insufficient():
    frame = pd.DataFrame([{"data_mode": "REAL", "model": "faas", "scenario": "idle", "endpoint": "read", "run_id": "r", "classification": "application_first_request", "latency_ms": 1000, "handler_ms": 20, "wall_ms": 1001}])
    table, penalty = cold_warm_analysis(frame)
    assert penalty.iloc[0]["status"] == "INSUFFICIENT_DATA"
    assert "confirmed_cold" not in set(table["classification"])
