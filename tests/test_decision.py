from dataclasses import replace

import pytest
import yaml

from benchmark.decision_engine import Workload, recommend


@pytest.fixture
def policy():
    return yaml.safe_load(open("configs/decision_policy.yaml", encoding="utf-8"))


@pytest.fixture
def workload():
    return Workload(100000, .05, 2, .7, 200, None, "standard", "high", False, "medium", 100, 20, event_driven=True, evidence_scope_verified=True)


@pytest.fixture
def evidence():
    return {m: {"data_mode": "REAL", "number_of_runs": 5, "p95_ci_upper_ms": 100, "achieved_rps": 100, "error_rate_pct": .1, "cold_p95_ms": 300, "monthly_cost_usd": 60 if m == "iaas" else 20, "capacity_supported": True} for m in ("iaas", "paas", "faas")}


def test_no_data_inconclusive(workload, policy):
    assert recommend(workload, {}, policy)["recommendation"] == "INCONCLUSIVE"


def test_demo_cannot_be_empirical_recommendation(workload, evidence, policy):
    for ev in evidence.values():
        ev["data_mode"] = "DEMO"
    assert recommend(workload, evidence, policy)["recommendation"] == "INCONCLUSIVE"
    result = recommend(workload, evidence, policy, allow_demo=True)
    assert result["status"] == "DEMO_ONLY"


def test_os_control_filters_serverless(workload, evidence, policy):
    result = recommend(replace(workload, required_control="os"), evidence, policy)
    assert result["recommendation"] == "IAAS"


def test_monthly_volume_alone_never_decides(workload, evidence, policy):
    result = recommend(replace(workload, evidence_scope_verified=False), evidence, policy)
    assert result["recommendation"] == "INCONCLUSIVE"


def test_event_preference_breaks_equal_cost_tie(workload, evidence, policy):
    assert recommend(workload, evidence, policy)["recommendation"] == "FAAS"


def test_peak_capacity_and_sla_filter(workload, evidence, policy):
    assert recommend(replace(workload, peak_rps=1000), evidence, policy)["recommendation"] == "INCONCLUSIVE"
    assert recommend(replace(workload, latency_sla_ms=50), evidence, policy)["recommendation"] == "INCONCLUSIVE"


def test_unknown_cold_evidence_excludes_strict_tolerance(workload, evidence, policy):
    for ev in evidence.values():
        ev["cold_p95_ms"] = None
    assert recommend(replace(workload, cold_tolerance_ms=200), evidence, policy)["recommendation"] == "INCONCLUSIVE"
