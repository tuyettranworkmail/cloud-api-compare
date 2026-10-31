import numpy as np
import pandas as pd
import pytest

from benchmark.statistics.analysis import bootstrap_ci, describe_latency, per_run_summary


def test_percentiles_match_linear_definition():
    result = describe_latency([1, 2, 3, 4, 100])
    assert result["p50_ms"] == 3
    assert result["p95_ms"] == pytest.approx(80.8)
    assert result["p99_ms"] == pytest.approx(96.16)
    assert result["std_ms"] == pytest.approx(np.std([1, 2, 3, 4, 100], ddof=1))


def test_empty_zero_request_is_missing_not_zero_latency():
    assert np.isnan(describe_latency([])["p95_ms"])


def test_single_run_has_no_ci():
    result = bootstrap_ci([42])
    assert result["estimate"] == 42
    assert np.isnan(result["ci_lower"])
    assert result["status"] == "INSUFFICIENT_DATA"


def test_ci_uses_runs_reproducibly():
    first = bootstrap_ci([10, 20, 30, 40, 50], 2000, seed=12)
    assert first == bootstrap_ci([10, 20, 30, 40, 50], 2000, seed=12)
    assert first["estimate"] == 30
    assert first["ci_lower"] < 30 < first["ci_upper"]
    assert first["number_of_runs"] == 5


def test_constant_runs_have_exact_ci():
    result = bootstrap_ci([5] * 5)
    assert result["ci_lower"] == result["ci_upper"] == 5


def test_warmup_excluded_errors_retained_and_fixed_duration():
    frame = pd.DataFrame([
        {"run_id": "r", "endpoint": "read", "phase": "warmup", "latency_ms": 99999, "success": True, "classification": "unknown", "scenario_start_ms": np.nan},
        {"run_id": "r", "endpoint": "read", "phase": "measurement", "latency_ms": 10, "success": True, "classification": "confirmed_warm", "scenario_start_ms": np.nan},
        {"run_id": "r", "endpoint": "read", "phase": "measurement", "latency_ms": 100, "success": False, "classification": "unknown", "scenario_start_ms": np.nan},
    ])
    meta = {"r": {"scenario": "steady", "model": "iaas", "data_mode": "REAL", "measurement_seconds": 10, "rate": .2, "status": "COMPLETE", "load_level": "low"}}
    summary = per_run_summary(frame, meta, pd.DataFrame(), minimum_samples=1)
    row = summary.loc[summary["endpoint"] == "all"].iloc[0]
    assert row["request_count"] == 2
    assert row["mean_ms"] == 55
    assert row["error_rate_pct"] == 50
    assert row["achieved_rps"] == .2


def test_zero_request_run_does_not_disappear():
    frame = pd.DataFrame(columns=["run_id", "phase", "endpoint", "success", "latency_ms", "classification", "scenario_start_ms"])
    meta = {"r": {"scenario": "steady", "model": "iaas", "data_mode": "REAL", "measurement_seconds": 10, "rate": 5, "status": "COMPLETE", "load_level": "low"}}
    row = per_run_summary(frame, meta, pd.DataFrame()).iloc[0]
    assert row["request_count"] == 0
    assert row["achieved_rps"] == 0
    assert np.isnan(row["error_rate_pct"])
    assert not row["valid_for_comparison"]
