from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import google.auth
import httpx
from google.auth.transport.requests import Request
from google.cloud import logging_v2, monitoring_v3
from google.protobuf.json_format import MessageToDict

from benchmark.config import target_config
from benchmark.io import utcnow, write_json

RUN_METRICS = {
    "instance_count": "run.googleapis.com/container/instance_count",
    "startup_latency": "run.googleapis.com/container/startup_latencies",
    "cpu": "run.googleapis.com/container/cpu/utilizations",
    "memory": "run.googleapis.com/container/memory/utilizations",
    "request_latency": "run.googleapis.com/request_latencies",
    "request_count": "run.googleapis.com/request_count",
    "billable_instance_time": "run.googleapis.com/container/billable_instance_time",
}
VM_METRICS = {
    "cpu": "compute.googleapis.com/instance/cpu/utilization",
    "memory": "agent.googleapis.com/memory/percent_used",
    "uptime": "compute.googleapis.com/instance/uptime",
}


def rfc3339(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timestamp cần timezone")
    return dt.astimezone(timezone.utc)


def metric_filter(c: dict, model: str, metric: str) -> str:
    target = target_config(c, model)
    # Validate filter values rather than allowing Monitoring filter injection.
    value = target["instance_id"] if model == "iaas" else target["service"]
    if not value or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for ch in value):
        raise ValueError("Cần instance_id/service hợp lệ trong targets.yaml")
    resource = "gce_instance" if model == "iaas" else "cloud_run_revision"
    label = "instance_id" if model == "iaas" else "service_name"
    location = f'resource.labels.zone = "{target["zone"]}"' if model == "iaas" else f'resource.labels.location = "{c["targets"]["region"]}"'
    return f'metric.type = "{metric}" AND resource.type = "{resource}" AND resource.labels.{label} = "{value}" AND {location}'


def collect_metrics(c: dict, model: str, start: str, end: str, output: Path, client=None) -> dict:
    client = client or monitoring_v3.MetricServiceClient()
    target = target_config(c, model)
    interval = monitoring_v3.TimeInterval(start_time=rfc3339(start), end_time=rfc3339(end))
    result = {"data_mode": "REAL", "model": model, "start": start, "end": end, "collected_at": utcnow(), "series": [], "metric_status": {}, "sampling_seconds": 60, "visibility_delay_seconds": 120}
    for alias, metric in (VM_METRICS if model == "iaas" else RUN_METRICS).items():
        try:
            series = list(client.list_time_series(request={"name": f'projects/{target["project"]}', "filter": metric_filter(c, model, metric), "interval": interval, "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL}, timeout=60))
            for item in series:
                # Preserve distributions, bucket boundaries, labels and per-point intervals.
                result["series"].append({"alias": alias, **MessageToDict(item._pb, preserving_proto_field_name=True)})
            result["metric_status"][alias] = "OK" if series else "NO_DATA"
        except Exception as error:
            result["metric_status"][alias] = f"ERROR:{type(error).__name__}"
    write_json(output, result)
    return result


def resource_snapshot(c: dict, model: str) -> dict:
    """Fetch authoritative VM / Cloud Run v2 / functions v2 settings with ADC."""
    target = target_config(c, model)
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform.read-only"])
    credentials.refresh(Request())
    base = f'projects/{target["project"]}/locations/{c["targets"]["region"]}'
    with httpx.Client(headers={"Authorization": f"Bearer {credentials.token}"}, timeout=30) as client:
        if model == "iaas":
            url = f'https://compute.googleapis.com/compute/v1/projects/{target["project"]}/zones/{target["zone"]}/instances/{target["instance_name"]}'
            response = client.get(url)
            response.raise_for_status()
            obj = response.json()
            machine = client.get("https://compute.googleapis.com/compute/v1/" + obj["machineType"].split("/compute/v1/")[-1])
            machine.raise_for_status()
            detail = machine.json()
            return {"verified_at": utcnow(), "instance_id": str(obj["id"]), "machine_type": obj["machineType"], "vm_vcpu": detail["guestCpus"], "vm_memory_mib": detail["memoryMb"], "status": obj["status"], "app_limits": "VERIFY_WITH_DOCKER_INSPECT", "declared": target["declared"]}
        function = None
        service = target["service"]
        if model == "faas":
            response = client.get(f'https://cloudfunctions.googleapis.com/v2/{base}/functions/{target["function_name"]}')
            response.raise_for_status()
            function = response.json()
            if function.get("environment") != "GEN_2":
                raise ValueError("FaaS phải là GEN_2")
            service = function["serviceConfig"]["service"].split("/")[-1]
        response = client.get(f"https://run.googleapis.com/v2/{base}/services/{service}")
        response.raise_for_status()
        obj = response.json()
        template = obj["template"]
        # Never persist environment variables / secrets / raw deployment objects.
        return {"verified_at": utcnow(), "service": service, "generation": obj.get("generation"), "latest_ready_revision": obj.get("latestReadyRevision"), "scaling": template.get("scaling", {}), "service_scaling": obj.get("scaling", {}), "concurrency": template.get("maxInstanceRequestConcurrency"), "timeout": template.get("timeout"), "containers": [{"image": item.get("image"), "resources": item.get("resources", {})} for item in template["containers"]], "runtime": function.get("buildConfig", {}).get("runtime") if function else target["runtime"], "function_service_config": {k: v for k, v in function["serviceConfig"].items() if k in {"availableCpu", "availableMemory", "maxInstanceCount", "minInstanceCount", "maxInstanceRequestConcurrency", "timeoutSeconds"}} if function else None, "declared": target["declared"]}


def collect_logs(c: dict, model: str, start: str, end: str, output: Path) -> dict:
    target = target_config(c, model)
    resource = "gce_instance" if model == "iaas" else "cloud_run_revision"
    label = f'resource.labels.instance_id="{target["instance_id"]}"' if model == "iaas" else f'resource.labels.service_name="{target["service"]}"'
    query = f'resource.type="{resource}" AND {label} AND timestamp>="{start}" AND timestamp<="{end}" AND jsonPayload.request_id:*'
    limit = c["experiments"]["monitoring"]["max_log_entries"]
    client = logging_v2.Client(project=target["project"])
    output.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with output.open("w", encoding="utf-8") as stream:
        for entry in client.list_entries(filter_=query, max_results=limit):
            # Allowlist only the data contract, excluding arbitrary application secrets.
            payload = {k: v for k, v in entry.payload.items() if k in {"request_id", "instance_id", "deployment_model", "endpoint", "cold_start", "handler_duration_ms", "status_code", "platform_startup_confirmed", "cold_start_scope"}}
            stream.write(json.dumps({"timestamp": entry.timestamp.isoformat(), **payload}) + "\n")
            n += 1
    return {"entries": n, "possibly_truncated": n == limit}
