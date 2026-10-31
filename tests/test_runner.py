
import pytest

from benchmark.config import ConfigError, redact, validate_config
from benchmark.runner import execute_plan, plan_experiments, spending_bound


def test_plan_is_reproducible_randomized_and_sequential(config):
    first = plan_experiments(config)
    assert first == plan_experiments(config)
    assert len(first) == 75
    for i in range(0, len(first), 3):
        assert {p["model"] for p in first[i:i+3]} == {"iaas", "paas", "faas"}
    orders = {tuple(p["model"] for p in first[i:i+3]) for i in range(0, len(first), 3)}
    assert len(orders) > 1


def test_dry_run_does_not_contact_cloud_or_create_raw(config, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Cloud must not be contacted")
    monkeypatch.setattr("benchmark.runner.validate_contracts", forbidden)
    result = execute_plan(config, plan_experiments(config, repeats=1), tmp_path, dry_run=True)
    assert result["cloud_contacted"] is False
    assert not (tmp_path / "raw").exists()


def test_missing_budget_bound_blocks(config):
    with pytest.raises(ConfigError):
        spending_bound(config, plan_experiments(config, repeats=1)[0])


def test_budget_bound_formula(config):
    config["experiments"]["safety"].update(verified_upper_usd_per_request=.001, verified_upper_usd_per_hour=1)
    p = plan_experiments(config, repeats=1)[0]
    assert spending_bound(config, p) == pytest.approx(p["request_bound"] * .001 + p["wall_bound_seconds"] / 3600)


def test_invalid_mix_rejected(config):
    config["workloads"]["mix"]["read"] = .8
    with pytest.raises(ConfigError):
        validate_config(config)


def test_redaction_recursive():
    value = {"headers": {"Authorization": "secret"}, "token": "secret", "safe": [1]}
    assert "secret" not in str(redact(value))


def test_idle_plan_does_not_require_running_k6_during_idle(config):
    p = plan_experiments(config, scenarios=["idle"], models=["faas"], repeats=1)[0]
    assert p["idle_seconds"] == 1200
    assert p["offered_requests"] == 21
