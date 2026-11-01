
from benchmark.collectors.gcp import collect_metrics, metric_filter


def test_vm_metric_filter_never_uses_run_resources(config):
    config["targets"]["targets"]["iaas"]["instance_id"] = "123456"
    value = metric_filter(config, "iaas", "compute.googleapis.com/instance/cpu/utilization")
    assert 'resource.type = "gce_instance"' in value
    assert "cloud_run_revision" not in value


def test_no_data_and_errors_are_recorded(config, tmp_path):
    config["targets"]["targets"]["paas"]["service"] = "test-service"
    class EmptyClient:
        def list_time_series(self, **kwargs):
            return []
    result = collect_metrics(config, "paas", "2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z", tmp_path / "metrics.json", client=EmptyClient())
    assert result["series"] == []
    assert set(result["metric_status"].values()) == {"NO_DATA"}
