"""Resource evidence helpers. Configuration declarations are not measurements."""
from __future__ import annotations

from pathlib import Path

from benchmark.io import read_json


def validate_container_evidence(path: Path, instance_id: str, app_vcpu=1, memory_gib=1) -> dict:
    data = read_json(path)
    if data.get("instance_id") != instance_id:
        raise ValueError("Container evidence không khớp instance_id")
    if data.get("cpu_limit") is None or abs(data["cpu_limit"] - app_vcpu) > .01 or data["memory_bytes"] != memory_gib * 2**30:
        raise ValueError("Container limits không khớp chế độ controlled")
    return data


def fairness_report(c: dict, snapshots: dict) -> dict:
    issues = []
    limits = {}
    vm_target = c["targets"]["targets"]["iaas"]
    evidence = vm_target.get("runtime_evidence_file")
    if evidence:
        vm = validate_container_evidence(Path(evidence), snapshots["iaas"]["instance_id"], vm_target["declared"]["app_vcpu"], vm_target["declared"]["app_memory_gib"])
        limits["iaas"] = {"cpu": vm["cpu_limit"], "memory_gib": vm["memory_bytes"] / 2**30}
    else:
        issues.append("IaaS container CPU/RAM chưa được kiểm chứng bằng docker inspect")
    for model in ("paas", "faas"):
        snapshot = snapshots[model]
        resources = snapshot["containers"][0]["resources"].get("limits", {})
        memory = resources.get("memory", "")
        try:
            memory_gib = float(memory[:-2]) if memory.endswith("Gi") else float(memory[:-2]) / 1024 if memory.endswith("Mi") else float(memory) / 2**30
            cpu = float(resources["cpu"])
        except (ValueError, KeyError):
            issues.append(f"{model}: không đọc được CPU/memory allocation")
            continue
        limits[model] = {"cpu": cpu, "memory_gib": memory_gib}
    if len(limits) != 3 or len({(v["cpu"], v["memory_gib"]) for v in limits.values()}) != 1:
        issues.append("Giới hạn ứng dụng chưa được xác minh tương đương")
    concurrency = {m: snapshots[m].get("concurrency") for m in ("paas", "faas")}
    if any(v is None for v in concurrency.values()) or len(set(concurrency.values())) > 1:
        issues.append("Concurrency PaaS/FaaS chưa được xác minh tương đương")
    return {"comparison_mode": c["experiments"]["comparison_mode"], "controlled_limits_verified": not issues, "limits": limits, "concurrency": concurrency, "issues": issues, "remaining_confounders": ["Worker count and app startup flags require team verification", "Underlying hardware/scheduler differ across services", "VM billed capacity remains full host; app limits do not equal billing allocation"]}
