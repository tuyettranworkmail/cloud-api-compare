import pytest

from benchmark.fairness import fairness_report, validate_container_evidence
from benchmark.io import write_json


def test_evidence_checks_instance_id_and_actual_limits(tmp_path):
    path = tmp_path / "limits.json"
    write_json(path, {"instance_id": "123", "cpu_limit": 1, "memory_bytes": 2**30})
    assert validate_container_evidence(path, "123")["cpu_limit"] == 1
    with pytest.raises(ValueError):
        validate_container_evidence(path, "456")


def test_controlled_cannot_claim_equivalence_without_evidence(config):
    snap = {"iaas": {"instance_id": "123"}, "paas": {"containers": [{"resources": {"limits": {"cpu": "1", "memory": "1Gi"}}}], "concurrency": 10}, "faas": {"containers": [{"resources": {"limits": {"cpu": "1", "memory": "1Gi"}}}], "concurrency": 80}}
    result = fairness_report(config, snap)
    assert not result["controlled_limits_verified"]
    assert any("Concurrency" in issue for issue in result["issues"])
