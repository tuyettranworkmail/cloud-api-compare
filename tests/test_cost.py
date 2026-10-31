
import numpy as np
import pytest

from benchmark.cost import PriceMissingError, find_intersections


def test_vm_full_host_cost_not_container_fraction(cost_model):
    result = cost_model.estimate("iaas", 0)
    assert result["compute_usd"] == pytest.approx(730 * .08266614)
    assert result["breakdown"]["disk"] == pytest.approx(10 * .044)
    assert result["cost_per_million_usd"] is None
    assert result["capacity_status"] == "UNVERIFIED"


def test_faas_gen2_same_cost_as_paas_when_same_config(cost_model):
    for n in (0, 100000, 2000000, 20000000):
        assert cost_model.estimate("paas", n)["total_usd"] == cost_model.estimate("faas", n)["total_usd"]


def test_missing_selected_price_errors_not_zero(cost_model):
    cost_model.catalog["rates"]["vm_hour"]["unit_price"] = None
    with pytest.raises(PriceMissingError):
        cost_model.estimate("iaas", 100)


def test_missing_unused_sku_does_not_break_zero_usage(cost_model):
    assert cost_model.price("egress_gib", 0) == 0
    with pytest.raises(PriceMissingError):
        cost_model.price("egress_gib", 1)


def test_firestore_exact_operation_formula(cost_model):
    result = cost_model.estimate("iaas", 100000)
    assert result["breakdown"]["firestore_read"] == pytest.approx(70000 * .000000369)
    assert result["breakdown"]["firestore_write"] == pytest.approx(20000 * .000001107)


def test_free_tier_requires_eligibility(cost_model):
    cost_model.workload["assumptions"]["free_tier"] = True
    with pytest.raises(ValueError):
        cost_model.estimate("paas", 100)


def test_free_tier_tier2_monetary_credit(cost_model):
    a = cost_model.workload["assumptions"]
    a.update(free_tier=True, free_tier_eligible=True, firestore_free_eligible=True)
    cost_model.workload["models"]["paas"].update(measured_active_instance_seconds=200000, min_instances=0)
    result = cost_model.estimate("paas", 1000)
    assert result["breakdown"]["compute_cpu"] == pytest.approx(200000 * .0000336 - 4.32)
    assert result["breakdown"]["requests"] == 0
    assert result["breakdown"]["firestore_read"] == 0


def test_firestore_daily_quota_not_monthly_pool(cost_model):
    a = cost_model.workload["assumptions"]
    a.update(free_tier=True, free_tier_eligible=True, firestore_free_eligible=True, days=1)
    result = cost_model.estimate("iaas", 100000)
    assert result["breakdown"]["firestore_read"] == pytest.approx(20000 * .000000369)


def test_instance_billing_has_no_request_charge(cost_model):
    cost_model.workload["models"]["paas"]["billing_mode"] = "instance"
    assert cost_model.estimate("paas", 2e6)["breakdown"]["requests"] == 0


def test_concurrency_not_full_division_at_sparse_traffic(cost_model):
    model = cost_model.workload["models"]["paas"]
    model["concurrency"] = 1
    first = cost_model.estimate("paas", 100)["billable_active_instance_seconds"]
    model["concurrency"] = 80
    second = cost_model.estimate("paas", 100)["billable_active_instance_seconds"]
    assert second > first * .9


def test_traffic_profile_changes_instance_cost(cost_model):
    cost_model.workload["models"]["paas"]["billing_mode"] = "instance"
    uniform = cost_model.estimate("paas", 2e6)["total_usd"]
    cost_model.workload["assumptions"]["distribution"] = "business"
    business = cost_model.estimate("paas", 2e6)["total_usd"]
    assert uniform != business


def test_capacity_fail_does_not_pretend_one_vm_suffices(cost_model):
    cost_model.workload["models"]["iaas"]["capacity_rps"] = .1
    assert cost_model.estimate("iaas", 2e7)["capacity_status"] == "UNSUPPORTED_CAPACITY"


@pytest.mark.parametrize("left,right,expected", [(lambda x: 10, lambda x: x, 10), (lambda x: 2 * x + 1, lambda x: x + 1, 0)])
def test_break_even_known_roots(left, right, expected):
    result = find_intersections(left, right, 0, 100)
    assert any(abs(x - expected) < 1e-5 for x in result["roots"])


def test_no_intersection_and_coincident_and_multiple():
    assert find_intersections(lambda x: x + 1, lambda x: x + 2, 0, 100)["status"] == "NO_INTERSECTION_IN_DOMAIN"
    result = find_intersections(lambda x: x, lambda x: x, 0, 100)
    assert result["coincident_intervals"] == [[0, 100]]
    result = find_intersections(lambda x: (x - 2) * (x - 10), lambda x: 0, 0, 100)
    assert len(result["roots"]) == 2


def test_discontinuous_sign_change_is_not_fake_root():
    result = find_intersections(lambda x: -1 if x < 10 else 1, lambda x: 0, 0, 100)
    assert result["roots"] == []
    assert len(result["discontinuities"]) == 1


def test_negative_and_nonfinite_requests_rejected(cost_model):
    for n in (-1, np.nan, np.inf):
        with pytest.raises(ValueError):
            cost_model.estimate("iaas", n)
