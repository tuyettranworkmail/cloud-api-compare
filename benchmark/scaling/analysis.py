from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from benchmark.io import read_json


def monitoring_frame(path: Path, meta: dict) -> pd.DataFrame:
    raw = read_json(path)
    if raw.get("data_mode") != meta["data_mode"]:
        raise ValueError("Monitoring và request data_mode không đồng nhất")
    rows = []
    for series in raw.get("series", []):
        for point in series.get("points", []):
            value = point["value"]
            scalar = value.get("double_value", value.get("int64_value"))
            distribution = value.get("distribution_value", {})
            rows.append({"data_mode": meta["data_mode"], "run_id": meta["run_id"], "model": meta["model"], "metric": series["alias"], "timestamp": point["interval"]["end_time"], "interval_start": point["interval"].get("start_time"), "value": float(scalar) if scalar is not None else distribution.get("mean", np.nan), "distribution_count": distribution.get("count"), "state": series.get("metric", {}).get("labels", {}).get("state", ""), "revision": series.get("resource", {}).get("labels", {}).get("revision_name", ""), "unit": series.get("unit", ""), "sampling_seconds": raw.get("sampling_seconds", 60)})
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        # Instance_count includes active+idle and all revisions; never take max of a single series.
        count = frame["metric"].eq("instance_count")
        summed = frame[count].groupby(["data_mode", "run_id", "model", "metric", "timestamp", "sampling_seconds"], as_index=False)["value"].sum()
        frame = pd.concat([frame[~count], summed], ignore_index=True)
    return frame


def analyze_scaling(frame: pd.DataFrame, meta: dict) -> dict:
    result = {"data_mode": meta["data_mode"], "run_id": meta["run_id"], "model": meta["model"], "scenario": meta["scenario"], "status": "INSUFFICIENT_DATA", "scale_out_seconds": np.nan, "scale_out_lower_seconds": np.nan, "scale_out_upper_seconds": np.nan, "baseline_instances": np.nan, "peak_instances": np.nan, "recovery_seconds": np.nan}
    if meta["model"] == "iaas":
        return {**result, "status": "NOT_APPLICABLE_FIXED_VM"}
    if meta["scenario"] != "burst":
        return {**result, "status": "NOT_APPLICABLE_SCENARIO"}
    if frame.empty:
        return result
    series = frame.loc[frame["metric"] == "instance_count"].sort_values("timestamp")
    if series.empty:
        return result
    start_string = meta.get("measurement_started_at")
    if start_string is None:
        start = pd.Timestamp(meta["k6_started_at"]) + pd.Timedelta(seconds=meta.get("warmup_seconds", 0))
    else:
        start = pd.Timestamp(start_string)
    burst = start + pd.to_timedelta(float(meta["baseline_seconds"]), unit="s")
    before = series.loc[series["timestamp"] <= burst]
    after = series.loc[series["timestamp"] > burst]
    if before.empty or after.empty:
        return result
    baseline = float(before.iloc[-1]["value"])
    increased = after.loc[after["value"] > baseline]
    sampling = float(series["sampling_seconds"].max())
    result.update(baseline_instances=baseline, peak_instances=float(after["value"].max()), sampling_seconds=sampling, burst_started_at=burst.isoformat())
    if increased.empty:
        return {**result, "status": "NO_SCALE_OBSERVED"}
    first = increased.iloc[0]
    previous = series.loc[series["timestamp"] < first["timestamp"]].iloc[-1]
    upper = (first["timestamp"] - burst).total_seconds()
    lower = max(0, (previous["timestamp"] - burst).total_seconds())
    result.update(status="OBSERVED_INTERVAL", scale_out_seconds=upper, scale_out_lower_seconds=lower, scale_out_upper_seconds=upper, observed_increase_at=first["timestamp"].isoformat(), peak_at=after.loc[after["value"].idxmax(), "timestamp"].isoformat())
    burst_end = burst + pd.to_timedelta(float(meta["ramp_seconds"] * 2 + meta["hold_seconds"]), unit="s")
    recovered = series.loc[(series["timestamp"] > burst_end) & (series["value"] <= baseline)]
    if not recovered.empty:
        result["recovery_seconds"] = (recovered.iloc[0]["timestamp"] - burst_end).total_seconds()
    return result


def cold_warm_analysis(frame: pd.DataFrame, resamples=2000, seed=20261031) -> tuple[pd.DataFrame, pd.DataFrame]:
    from benchmark.statistics.analysis import bootstrap_ci, describe_latency
    rows, penalties = [], []
    for key, group in frame.groupby(["data_mode", "model", "scenario", "endpoint", "run_id"]):
        common = dict(zip(["data_mode", "model", "scenario", "endpoint", "run_id"], key))
        for classification, part in group.groupby("classification"):
            summary = describe_latency(part["latency_ms"])
            if len(part) < 20:
                summary["p95_ms"] = np.nan
            if len(part) < 1000:
                summary["p99_ms"] = np.nan
            rows.append({**common, "classification": classification, "request_count": len(part), **summary, "tail_warning": "p95 requires >=20, p99 requires >=1000 samples; no guarantees at these minimums", "handler_mean_ms": part["handler_ms"].mean(), "wall_mean_ms": part["wall_ms"].mean()})
    table = pd.DataFrame(rows)
    for key, group in frame.groupby(["data_mode", "model", "scenario", "endpoint"]):
        differences = []
        for run_id, part in group.groupby("run_id"):
            cold = part.loc[part["classification"].eq("confirmed_cold"), "latency_ms"]
            warm = part.loc[part["classification"].eq("confirmed_warm"), "latency_ms"]
            if len(cold) >= 1 and len(warm) >= 5:
                differences.append(float(cold.median() - warm.median()))
        result = bootstrap_ci(differences, resamples, seed)
        if len(differences) < 5:
            result.update(status="INSUFFICIENT_DATA", ci_lower=np.nan, ci_upper=np.nan)
        penalties.append({**dict(zip(["data_mode", "model", "scenario", "endpoint"], key)), **result, "method": "mean paired-run difference of cold/warm medians; distribution association, not isolated infrastructure startup"})
    return table, pd.DataFrame(penalties)


def burst_response_analysis(frame: pd.DataFrame, metadata: dict, *, window_seconds=10, degradation_factor=1.5) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Latency degradation onset/recovery using declared bins and exact stage cohorts."""
    responses, stages = [], []
    for run_id, meta in metadata.items():
        if meta["scenario"] != "burst":
            continue
        common = {"data_mode": meta["data_mode"], "run_id": run_id, "model": meta["model"]}
        group = frame.loc[frame["run_id"].eq(run_id)].copy()
        result = {**common, "status": "INSUFFICIENT_DATA", "degradation_onset_seconds": np.nan, "latency_recovery_seconds": np.nan, "observation_window_seconds": window_seconds, "degradation_factor": degradation_factor, "degradation_offered_rps": np.nan}
        if group.empty:
            responses.append(result)
            continue
        values = group["scenario_start_ms"].dropna()
        start = pd.to_datetime(values.iloc[0], unit="ms", utc=True) if len(values) else pd.Timestamp(meta["measurement_started_at"])
        # Stage membership based on request initiation, not completion after a stage.
        wall = group["wall_ms"].fillna(group["latency_ms"])
        group["seconds"] = (group["timestamp"] - pd.to_timedelta(wall, unit="ms") - start).dt.total_seconds()
        burst = meta["baseline_seconds"]
        ramp_end = burst + meta["ramp_seconds"]
        hold_end = ramp_end + meta["hold_seconds"]
        recovery_start = hold_end + meta["ramp_seconds"]
        group["stage"] = np.select([group["seconds"] < burst, group["seconds"] < ramp_end, group["seconds"] < hold_end, group["seconds"] < recovery_start], ["baseline", "ramp_up", "hold", "ramp_down"], default="recovery")
        durations = {"baseline": meta["baseline_seconds"], "ramp_up": meta["ramp_seconds"], "hold": meta["hold_seconds"], "ramp_down": meta["ramp_seconds"], "recovery": meta["recovery_seconds"]}
        for stage, part in group.groupby("stage"):
            stages.append({**common, "stage": stage, "request_count": len(part), "p95_ms": part["latency_ms"].quantile(.95), "p99_ms": part["latency_ms"].quantile(.99), "error_rate_pct": 100 * part["success"].eq(False).mean(), "cohort_rps": len(part) / durations[stage] if durations[stage] else np.nan})
        baseline = group.loc[group["stage"] == "baseline", "latency_ms"]
        if len(baseline) < 20:
            responses.append(result)
            continue
        baseline_p95 = baseline.quantile(.95)
        bins = group.loc[group["seconds"] >= burst].copy()
        bins["bin"] = np.floor((bins["seconds"] - burst) / window_seconds) * window_seconds + burst
        stats = bins.groupby("bin")["latency_ms"].agg(p95=lambda x: x.quantile(.95), count="size")
        stats = stats.loc[stats["count"] >= 20]
        degraded = stats.loc[stats["p95"] > baseline_p95 * degradation_factor]
        result.update(status="NO_DEGRADATION_OBSERVED", baseline_p95_ms=baseline_p95)
        if not degraded.empty:
            onset = float(degraded.index[0])
            rate = meta["peak_rps"] if onset >= ramp_end else meta["baseline_rps"] + (meta["peak_rps"] - meta["baseline_rps"]) * max(0, onset - burst) / max(1e-9, meta["ramp_seconds"])
            result.update(status="DEGRADATION_OBSERVED", degradation_onset_seconds=onset - burst, degradation_offered_rps=rate)
            recovery = stats.loc[stats.index >= recovery_start]
            acceptable = recovery["p95"] <= baseline_p95 * degradation_factor
            # Require two adjacent acceptable windows; isolated good bins do not establish recovery.
            for index in range(len(recovery) - 1):
                if acceptable.iloc[index] and acceptable.iloc[index + 1] and recovery.index[index + 1] - recovery.index[index] == window_seconds:
                    result["latency_recovery_seconds"] = float(recovery.index[index] - recovery_start)
                    break
        responses.append(result)
    return pd.DataFrame(responses), pd.DataFrame(stages)
