from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from benchmark.io import DEMO_LABEL, write_json
from benchmark.parsers import load_dataset
from benchmark.scaling.analysis import analyze_scaling, burst_response_analysis, cold_warm_analysis, monitoring_frame


def describe_latency(values) -> dict:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if not len(x):
        return {k: np.nan for k in ("mean_ms", "p50_ms", "p95_ms", "p99_ms", "min_ms", "max_ms", "std_ms", "cv")}
    p50, p95, p99 = np.quantile(x, [0.5, 0.95, 0.99], method="linear")
    std = float(np.std(x, ddof=1)) if len(x) > 1 else np.nan
    mean = float(np.mean(x))
    return {"mean_ms": mean, "p50_ms": p50, "p95_ms": p95, "p99_ms": p99, "min_ms": float(np.min(x)), "max_ms": float(np.max(x)), "std_ms": std, "cv": std / mean if mean else np.nan}


def bootstrap_ci(values, resamples=2000, seed=20261031) -> dict:
    """Bootstrap MEAN of independent run-level metrics; never request pseudoreplication."""
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    result = {"estimate": float(np.mean(x)) if len(x) else np.nan, "ci_lower": np.nan, "ci_upper": np.nan, "number_of_runs": len(x), "bootstrap_method": "percentile_bootstrap_of_independent_run_means", "resamples": resamples, "status": "INSUFFICIENT_DATA"}
    if len(x) < 2:
        return result
    rng = np.random.default_rng(seed)
    # Bound memory at 10k runs/resample block.
    estimates = np.concatenate([rng.choice(x, size=(min(250, resamples - i), len(x)), replace=True).mean(axis=1) for i in range(0, resamples, 250)])
    result.update(ci_lower=float(np.quantile(estimates, 0.025)), ci_upper=float(np.quantile(estimates, 0.975)), status="OK" if len(x) >= 5 else "FEW_RUNS")
    return result


def offered_measurement(meta: dict) -> float:
    if meta["scenario"] == "burst":
        return meta["baseline_rps"] * (meta["baseline_seconds"] + meta["recovery_seconds"]) + meta["ramp_seconds"] * (meta["baseline_rps"] + meta["peak_rps"]) + meta["hold_seconds"] * meta["peak_rps"]
    if meta["scenario"] == "idle":
        return meta["warm_requests"] + 1
    return meta["rate"] * meta["measurement_seconds"]


def per_run_summary(frame: pd.DataFrame, metadata: dict, metrics: pd.DataFrame, minimum_samples=30) -> pd.DataFrame:
    rows = []
    for run_id, meta in metadata.items():
        measured = frame.loc[(frame["run_id"] == run_id) & frame["phase"].isin(["measurement", "first_after_idle"])]
        duration = float(meta["measurement_seconds"])
        if meta["scenario"] == "idle" and len(measured) > 0:
            wall = pd.to_numeric(measured["wall_ms"], errors="coerce").fillna(measured["latency_ms"])
            duration = max(1e-9, (measured["timestamp"].max() - (measured["timestamp"] - pd.to_timedelta(wall, unit="ms")).min()).total_seconds())
        dropped = 0
        if not metrics.empty:
            selected = metrics.loc[(metrics["run_id"] == run_id) & metrics["metric"].eq("dropped_iterations")]
            selected = selected.loc[selected["tags"].map(lambda tags: tags.get("scenario", "measurement") != "warmup")]
            dropped = int(selected["value"].sum())
        offered = offered_measurement(meta)
        for endpoint in ["all", *sorted(set(measured["endpoint"]))]:
            group = measured if endpoint == "all" else measured.loc[measured["endpoint"] == endpoint]
            n = len(group)
            success = int(group["success"].eq(True).sum())
            unknown = int(group["success"].isna().sum())
            failed = n - success - unknown
            fraction = 1 if endpoint == "all" or meta.get("endpoint") == endpoint else meta.get("mix", {"read": .7, "write": .2, "cpu": .1}).get(endpoint, np.nan)
            count_within = n
            if meta["scenario"] != "idle" and n and group["scenario_start_ms"].notna().any():
                end = pd.to_datetime(group["scenario_start_ms"].dropna().iloc[0], unit="ms", utc=True) + pd.to_timedelta(duration, unit="s")
                count_within = int(group["timestamp"].le(end).sum())
            valid = meta.get("status") == "COMPLETE" and meta.get("ingestion_valid", True) and dropped == 0 and n >= minimum_samples and unknown == 0
            row = {"data_mode": meta["data_mode"], "run_id": run_id, "model": meta["model"], "scenario": meta["scenario"], "load_level": meta["load_level"], "endpoint": endpoint, "repeat": meta.get("repeat"), "request_count": n, "success_count": success, "failure_count": failed, "unknown_outcome_count": unknown, **describe_latency(group["latency_ms"]), "duration_seconds": duration, "offered_rps": offered * fraction / duration if meta["scenario"] != "idle" else np.nan, "achieved_rps": count_within / duration, "cohort_rps": n / duration, "goodput_rps": success / duration, "error_rate_pct": 100 * failed / n if n else np.nan, "dropped_iterations": dropped if endpoint == "all" else np.nan, "dropped_rate_pct": 100 * dropped / offered if offered and endpoint == "all" else np.nan, "cold_count": int(group["classification"].eq("confirmed_cold").sum()), "cold_ratio_pct": 100 * group["classification"].eq("confirmed_cold").sum() / n if n else np.nan, "unknown_classification_count": int(group["classification"].eq("unknown").sum()), "valid_for_comparison": valid, "status": meta.get("status"), "p99_warning": "UNSTABLE_SMALL_SAMPLE" if n < 1000 else "", "warning": "DROPPED_ITERATIONS" if dropped else "INSUFFICIENT_SAMPLES" if n < minimum_samples else "UNKNOWN_OUTCOMES" if unknown else ""}
            if n and meta["scenario"] != "idle" and endpoint == "all" and offered and n / offered < .98:
                row["valid_for_comparison"] = False
                row["warning"] += "; UNDER_OFFERED_OR_INCOMPLETE"
            rows.append(row)
    return pd.DataFrame(rows)


def between_runs(per_run: pd.DataFrame, resamples=2000, seed=20261031) -> pd.DataFrame:
    rows = []
    keys = ["data_mode", "model", "scenario", "load_level", "endpoint"]
    if per_run.empty:
        return pd.DataFrame(columns=keys + ["metric", "estimate", "ci_lower", "ci_upper", "number_of_runs", "sample_size"])
    valid = per_run.loc[per_run["valid_for_comparison"]]
    for key, group in valid.groupby(keys, dropna=False):
        for metric in ("p50_ms", "p95_ms", "p99_ms", "mean_ms", "achieved_rps", "error_rate_pct"):
            rows.append({**dict(zip(keys, key)), "metric": metric, **bootstrap_ci(group[metric], resamples, seed), "sample_size": int(group["request_count"].sum()), "estimand": "mean_of_run_statistics"})
    return pd.DataFrame(rows)


def timeline_summary(frame: pd.DataFrame, metadata: dict, bin_seconds=10) -> pd.DataFrame:
    rows = []
    for run_id, meta in metadata.items():
        group = frame.loc[frame["run_id"].eq(run_id) & frame["phase"].isin(["measurement", "first_after_idle"])].copy()
        if group.empty:
            continue
        first = group["scenario_start_ms"].dropna()
        start = pd.to_datetime(first.iloc[0], unit="ms", utc=True) if len(first) else group["timestamp"].min()
        group["relative_seconds"] = (group["timestamp"] - start).dt.total_seconds()
        group["bin"] = np.floor(group["relative_seconds"] / bin_seconds).astype(int) * bin_seconds
        for second, part in group.groupby("bin"):
            effective_width = min(bin_seconds, max(0, float(meta["measurement_seconds"]) - second))
            if effective_width <= 0:
                continue
            burst_start = meta.get("baseline_seconds", float("inf"))
            burst_end = burst_start + meta.get("ramp_seconds", 0) + meta.get("hold_seconds", 0)
            phase = "baseline" if second < burst_start else "burst" if second <= burst_end else "recovery"
            rows.append({"data_mode": meta["data_mode"], "run_id": run_id, "model": meta["model"], "scenario": meta["scenario"], "relative_seconds": second, "burst_phase": phase, "request_count": len(part), "achieved_rps": len(part) / effective_width, "p95_ms": part["latency_ms"].quantile(.95), "p99_ms": part["latency_ms"].quantile(.99), "error_rate_pct": 100 * part["success"].eq(False).mean()})
    return pd.DataFrame(rows)


def analyze(root: Path, output: Path, *, resamples=2000, minimum_samples=30, seed=20261031) -> dict[str, pd.DataFrame]:
    frame, metadata, metrics, quality = load_dataset(root)
    output.mkdir(parents=True, exist_ok=True)
    per_run = per_run_summary(frame, metadata, metrics, minimum_samples)
    comparison = between_runs(per_run, resamples, seed)
    series, scaling = [], []
    for run_id, meta in metadata.items():
        run_points = frame.loc[frame["run_id"].eq(run_id) & frame["phase"].eq("measurement"), "scenario_start_ms"].dropna()
        if len(run_points):
            meta["measurement_started_at"] = pd.to_datetime(run_points.iloc[0], unit="ms", utc=True).isoformat()
        path = Path(meta["source_directory"]) / "monitoring.json"
        monitor = monitoring_frame(path, meta) if path.exists() else pd.DataFrame()
        if not monitor.empty:
            series.append(monitor)
        scaling.append(analyze_scaling(monitor, meta))
    measured = frame.loc[frame["phase"].isin(["measurement", "first_after_idle"])]
    cold, penalty = cold_warm_analysis(measured, resamples, seed)
    burst_response, burst_phases = burst_response_analysis(measured, metadata)
    errors = measured.groupby(["data_mode", "model", "scenario", "endpoint", "status", "error_type"], dropna=False).size().reset_index(name="request_count")
    tables = {"requests": frame, "per_run": per_run, "comparison": comparison, "endpoint_summary": per_run.loc[per_run["endpoint"] != "all"] if not per_run.empty else per_run, "scenario_summary": per_run.loc[per_run["endpoint"] == "all"] if not per_run.empty else per_run, "cold_warm": cold, "cold_penalty": penalty, "scaling": pd.DataFrame(scaling), "burst_response": burst_response, "burst_phases": burst_phases, "monitoring": pd.concat(series, ignore_index=True) if series else pd.DataFrame(), "timeline": timeline_summary(frame, metadata), "errors": errors}
    for name, table in tables.items():
        table.to_csv(output / f"{name}.csv", index=False, encoding="utf-8-sig")
    write_json(output / "quality.json", quality)
    modes = sorted(set(m["data_mode"] for m in metadata.values()))
    label = "NO DATA — NOT EXECUTED" if not modes else DEMO_LABEL if "DEMO" in modes else "LOCAL TEST — NOT REAL CLOUD MEASUREMENTS" if "LOCAL_TEST" in modes else "REAL CLOUD MEASUREMENTS — inspect run validity"
    write_json(output / "provenance.json", {"input_root": str(root.resolve()), "data_modes": modes, "label": label, "runs": len(metadata), "valid_run_groups": int(per_run["valid_for_comparison"].sum()) if not per_run.empty else 0, "bootstrap_resamples": resamples, "bootstrap_seed": seed})
    return tables
