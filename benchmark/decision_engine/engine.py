from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class Workload:
    monthly_requests: int
    average_duration_seconds: float
    burstiness: float
    idle_ratio: float
    latency_sla_ms: float
    cold_tolerance_ms: float | None
    required_control: str
    operational_expertise: str
    long_running_background: bool
    portability: str
    budget_usd: float
    peak_rps: float
    event_driven: bool = False
    approved_models: tuple[str, ...] = ("iaas", "paas", "faas")
    evidence_scope_verified: bool = False


def recommend(workload: Workload, evidence: dict, policy: dict, *, allow_demo=False) -> dict:
    """Filter by measured SLA/capacity + costs + capabilities, then explain tradeoffs.

    evidence[model] requires data_mode, number_of_runs, p95_ci_upper_ms,
    achieved_rps, error_rate_pct, cold_p95_ms, monthly_cost_usd, capacity_supported.
    No empirical recommendation is made using simulated data by default.
    """
    w = workload
    if w.monthly_requests < 0 or w.average_duration_seconds < 0 or w.burstiness < 1 or not 0 <= w.idle_ratio < 1 or w.budget_usd < 0 or w.latency_sla_ms <= 0 or w.peak_rps < 0:
        raise ValueError("Workload không hợp lệ")
    if w.required_control not in {"standard", "os"} or w.operational_expertise not in {"low", "medium", "high"} or w.portability not in {"low", "medium", "high"}:
        raise ValueError("Control/expertise/portability không hợp lệ")
    output = {"recommendation": "INCONCLUSIVE", "status": "INSUFFICIENT_DATA", "reasons": [], "risks": [], "candidates": [], "exclusions": {}, "workload": asdict(w)}
    if not w.evidence_scope_verified:
        output["reasons"].append("Chưa xác nhận benchmark đại diện cho workload, cấu hình và traffic profile này")
        return output
    candidates = []
    for model, capability in policy["capabilities"].items():
        reasons = []
        ev = evidence.get(model, {})
        if model not in w.approved_models:
            reasons.append("Ngoài phạm vi security/compliance đã phê duyệt")
        if w.required_control == "os" and not capability["os_control"]:
            reasons.append("Cần quyền OS")
        if capability["min_ops_expertise"] == "high" and w.operational_expertise != "high":
            reasons.append("Chưa đủ nhân lực vận hành cấu hình này")
        if w.portability == "high" and capability["portability"] != "high":
            reasons.append("Yêu cầu portability cao")
        if w.long_running_background and not capability["background"]:
            reasons.append("Cấu hình hiện tại chưa xác minh background/lifetime billing")
        if not allow_demo and ev.get("data_mode") != "REAL":
            reasons.append("Cần số đo REAL")
        required = ["number_of_runs", "p95_ci_upper_ms", "achieved_rps", "error_rate_pct", "monthly_cost_usd", "capacity_supported"]
        if any(ev.get(key) is None for key in required):
            reasons.append("Thiếu bằng chứng latency/capacity/cost")
        else:
            if ev["number_of_runs"] < policy["minimum_runs"]:
                reasons.append("Chưa đủ số run độc lập")
            if ev["p95_ci_upper_ms"] > w.latency_sla_ms:
                reasons.append("p95 CI upper vượt SLA")
            if ev["achieved_rps"] < w.peak_rps or not ev["capacity_supported"]:
                reasons.append("Chưa chứng minh capacity tại peak")
            if ev["error_rate_pct"] > policy["maximum_error_rate_pct"]:
                reasons.append("Error rate vượt ngưỡng")
            if ev["monthly_cost_usd"] > w.budget_usd:
                reasons.append("Vượt budget")
            if w.cold_tolerance_ms is not None and (ev.get("cold_p95_ms") is None or ev["cold_p95_ms"] > w.cold_tolerance_ms):
                reasons.append("Cold latency chưa đạt hoặc chưa đo")
        if capability["max_request_seconds"] is None and w.average_duration_seconds > 60:
            reasons.append("Thời lượng dài cần xác minh timeout thực tế")
        elif capability["max_request_seconds"] is not None and w.average_duration_seconds > capability["max_request_seconds"]:
            reasons.append("Vượt timeout đã xác minh")
        if reasons:
            output["exclusions"][model] = reasons
        else:
            # Equal prices can legitimately produce equivalent candidates.
            candidates.append((model, ev["monthly_cost_usd"]))
    output["candidates"] = [model for model, _ in candidates]
    if not candidates:
        output["reasons"].append("Không có cấu hình nào vượt qua toàn bộ điều kiện/bằng chứng")
        return output
    minimum = min(cost for _, cost in candidates)
    tied = [model for model, cost in candidates if abs(cost - minimum) <= .01]
    if len(tied) > 1:
        preferred = "faas" if w.event_driven and w.idle_ratio >= .5 else "paas" if w.portability == "high" else None
        if preferred not in tied:
            output.update(status="EQUIVALENT_CANDIDATES", reasons=["Chi phí các ứng viên gần bằng nhau; cần thêm ưu tiên vận hành"])
            return output
        chosen = preferred
        output["reasons"].append("Chi phí ngang nhau; ưu tiên event-driven/portability của workload")
    else:
        chosen = tied[0]
    output.update(recommendation=chosen.upper(), status="DEMO_ONLY" if evidence[chosen].get("data_mode") == "DEMO" else "RECOMMENDED")
    output["reasons"].append("Đạt các điều kiện đã xác minh; chi phí ước tính thấp nhất trong tập phù hợp")
    output["risks"] = ["Chi phí là ước tính theo giả định đã khai báo", "Hiệu năng chỉ có giá trị trong phạm vi workload/cấu hình đã kiểm chứng", "Background, security và portability cần kiểm tra khi đổi cấu hình"]
    return output
