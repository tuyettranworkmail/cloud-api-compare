"""Read native k6 JSONL/CSV. Raw records are never modified."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

import numpy as np
import pandas as pd

from benchmark.io import read_json

REQUEST_COLUMNS = ["timestamp", "request_id", "run_id", "model", "scenario", "load_level", "endpoint", "phase", "latency_ms", "wall_ms", "handler_ms", "status", "success", "classification", "instance_id", "error_code", "data_mode", "scenario_start_ms"]


def parse_k6(path: Path, metadata: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    records, metrics = [], []
    errors = []
    mode = metadata.get("data_mode")
    if mode not in {"DEMO", "REAL", "LOCAL_TEST"}:
        raise ValueError("Raw dataset cần metadata.data_mode DEMO hoặc REAL")
    if path.suffix == ".csv":
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        points = []
        for index, row in frame.iterrows():
            raw = row.to_dict()
            metric = raw.pop("metric_name")
            timestamp_raw = raw.pop("timestamp")
            try:
                number = float(timestamp_raw)
                timestamp = pd.to_datetime(number, unit=metadata.get("csv_time_unit", "s"), utc=True).isoformat()
            except ValueError:
                timestamp = pd.to_datetime(timestamp_raw, utc=True).isoformat()
            value = float(raw.pop("metric_value"))
            # Native CSV has a JSON extra_tags column for custom tags.
            extra = raw.pop("extra_tags", "")
            if extra:
                raw.update(json.loads(extra) if extra.startswith("{") else dict(parse_qsl(extra, keep_blank_values=True)))
            points.append((index + 2, {"type": "Point", "metric": metric, "data": {"time": timestamp, "value": value, "tags": raw}}))
    else:
        def lines():
            with path.open(encoding="utf-8-sig") as stream:
                for number, line in enumerate(stream, 1):
                    if not line.strip():
                        continue
                    try:
                        yield number, json.loads(line)
                    except json.JSONDecodeError:
                        errors.append({"line": number, "reason": "MALFORMED_JSON"})
        points = lines()
    fallback = []
    for number, point in points:
        if point.get("type") != "Point":
            continue
        try:
            data, metric = point["data"], point["metric"]
            tags = data.get("tags") or {}
            metric_row = {"timestamp": data["time"], "metric": metric, "value": float(data["value"]), "tags": tags, "run_id": metadata["run_id"], "data_mode": mode}
            metrics.append(metric_row)
            if metric not in {"request_sample_ms", "http_req_duration"}:
                continue
            status = tags.get("status", "")
            success = tags.get("success")
            success = str(success).lower() == "true" if success is not None else (200 <= int(status) < 400 if status else None)
            record = {
                "timestamp": data["time"], "request_id": tags.get("request_id") or f'{metadata["run_id"]}-line-{number}',
                "run_id": metadata["run_id"], "model": metadata.get("model", tags.get("deployment_model")),
                "scenario": metadata.get("scenario", tags.get("scenario_name")), "load_level": metadata.get("load_level", tags.get("load_level", "unknown")),
                "endpoint": tags.get("endpoint", "unknown"), "phase": tags.get("phase", tags.get("scenario", "unknown")),
                "latency_ms": float(data["value"]), "wall_ms": tags.get("wall_ms"), "handler_ms": tags.get("handler_ms"),
                "status": status, "success": success, "classification": tags.get("classification", "unknown"),
                "instance_id": tags.get("instance_id", ""), "error_code": tags.get("error_code", ""), "data_mode": mode,
                "scenario_start_ms": tags.get("scenario_start_ms"),
            }
            (records if metric == "request_sample_ms" else fallback).append(record)
        except (ValueError, KeyError, TypeError):
            errors.append({"line": number, "reason": "INVALID_POINT"})
    if not records and fallback:
        records = fallback
        errors.append({"reason": "FALLBACK_DURATION_ONLY: business/wall/cold evidence may be unavailable"})
    return pd.DataFrame(records, columns=REQUEST_COLUMNS), pd.DataFrame(metrics, columns=["timestamp", "metric", "value", "tags", "run_id", "data_mode"]), {"parse_errors": errors}


def clean_requests(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    frame = raw.copy()
    if frame.empty:
        frame["error_type"] = pd.Series(dtype="str")
        frame["outlier"] = pd.Series(dtype="bool")
        return frame, {"input_rows": 0, "valid_rows": 0, "missing": {}, "duplicates": 0, "invalid_rows": 0}
    required = {"timestamp", "latency_ms", "request_id", "run_id", "data_mode", "status", "success"}
    if missing := required - set(frame.columns):
        raise ValueError(f"Thiếu cột: {sorted(missing)}")
    if not set(frame["data_mode"]).issubset({"DEMO", "REAL", "LOCAL_TEST"}):
        raise ValueError("data_mode không hợp lệ")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    for name in ("latency_ms", "wall_ms", "handler_ms", "status", "scenario_start_ms"):
        if name not in frame:
            frame[name] = np.nan
        frame[name] = pd.to_numeric(frame[name], errors="coerce")
    if frame["success"].dtype != bool:
        frame["success"] = frame["success"].map(lambda v: v if isinstance(v, bool) else str(v).lower() == "true" if pd.notna(v) and str(v).lower() in {"true", "false"} else None)
    missing_counts = frame.isna().sum().to_dict()
    identity = ["data_mode", "run_id", "request_id"]
    duplicate = frame.duplicated(identity, keep=False)
    exact = frame.duplicated(keep="first")
    conflicts = frame[duplicate & ~exact].groupby(identity, dropna=False).size()
    conflict_keys = set(conflicts[conflicts > 1].index)
    conflicting = frame[identity].apply(tuple, axis=1).isin(conflict_keys)
    invalid = frame["timestamp"].isna() | ~np.isfinite(frame["latency_ms"]) | (frame["latency_ms"] < 0) | frame["request_id"].isna() | frame["run_id"].isna() | conflicting
    report = {"input_rows": len(raw), "missing": missing_counts, "duplicates": int(exact.sum()), "conflicting_request_keys": len(conflict_keys), "invalid_rows": int(invalid.sum()), "quarantine_request_ids": frame.loc[invalid, "request_id"].astype(str).tolist()}
    frame = frame.loc[~invalid & ~exact].copy()
    frame["classification"] = frame["classification"].where(frame["classification"].isin(["confirmed_cold", "application_first_request", "confirmed_warm", "unknown"]), "unknown")
    frame["error_type"] = np.select([
        frame["error_code"].astype(str).isin(["1050", "1211"]) | frame["status"].eq(0),
        frame["status"].ge(400), frame["success"].eq(False), frame["success"].isna(),
    ], ["transport_or_timeout", "http_error", "business_error", "unknown"], default="none")
    # Retain outliers. Flagging uses within-run/endpoint IQR, not deletion.
    def outliers(series):
        q1, q3 = series.quantile([0.25, 0.75])
        return series.gt(q3 + 1.5 * (q3 - q1))
    frame["outlier"] = frame.groupby(["data_mode", "run_id", "endpoint"])["latency_ms"].transform(outliers)
    report.update(valid_rows=len(frame), outliers_retained=int(frame["outlier"].sum()), warmup_rows=int(frame["phase"].eq("warmup").sum()))
    return frame, report


def join_application_logs(frame: pd.DataFrame, path: Path) -> tuple[pd.DataFrame, dict]:
    logs = []
    errors = 0
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                obj = json.loads(line)
                logs.append(obj.get("jsonPayload", obj))
            except (ValueError, TypeError):
                errors += 1
    result = frame.copy()
    if not logs:
        return result, {"joined": 0, "invalid_logs": errors}
    table = pd.DataFrame(logs)
    if "request_id" not in table:
        return result, {"joined": 0, "invalid_logs": errors + len(logs)}
    duplicate = table["request_id"].duplicated(keep=False)
    table = table.loc[~duplicate].set_index("request_id")
    matched = result["request_id"].isin(table.index)
    # Only an independent, documented platform event may promote process-first.
    if "platform_startup_confirmed" in table:
        evidence = result["request_id"].map(table["platform_startup_confirmed"]).eq(True)
        result.loc[evidence & result["classification"].eq("application_first_request"), "classification"] = "confirmed_cold"
    if "handler_duration_ms" in table:
        values = pd.to_numeric(result["request_id"].map(table["handler_duration_ms"]), errors="coerce")
        result["handler_ms"] = result["handler_ms"].fillna(values)
    return result, {"joined": int(matched.sum()), "duplicate_log_ids_excluded": int(duplicate.sum()), "invalid_logs": errors}


def load_dataset(root: Path) -> tuple[pd.DataFrame, dict[str, dict], pd.DataFrame, dict[str, Any]]:
    raw_root = root / "raw" if (root / "raw").exists() else root
    metadata_files = sorted(raw_root.rglob("metadata.json"))
    selected: dict[str, tuple[Path, dict]] = {}
    for path in metadata_files:
        meta = read_json(path)
        key = meta["run_id"]
        if key not in selected or meta.get("attempt", 1) > selected[key][1].get("attempt", 1):
            selected[key] = (path, meta)
    requests, metric_frames, metadata, reports = [], [], {}, {}
    for run_id, (path, meta) in selected.items():
        source = path.parent / "k6.jsonl"
        if not source.exists():
            source = path.parent / "k6.csv"
        metadata[run_id] = {**meta, "source_directory": str(path.parent)}
        if not source.exists():
            reports[run_id] = {"status": "MISSING_RAW"}
            continue
        frame, metrics, parsing = parse_k6(source, meta)
        frame, cleaning = clean_requests(frame)
        metadata[run_id]["ingestion_valid"] = not parsing["parse_errors"] and cleaning["invalid_rows"] == 0
        log_report = {}
        if (path.parent / "application.jsonl").exists():
            frame, log_report = join_application_logs(frame, path.parent / "application.jsonl")
        requests.append(frame)
        # Request timing metrics stay losslessly in raw JSONL. Cross-run analysis
        # only needs scheduling counters/gauges here; avoid retaining millions of
        # duplicate timing-point dictionaries alongside the exact request table.
        metric_frames.append(metrics.loc[metrics["metric"].isin(["dropped_iterations", "vus", "vus_max"])].copy())
        reports[run_id] = {**parsing, **cleaning, "logs": log_report}
    return (pd.concat(requests, ignore_index=True) if requests else pd.DataFrame(columns=[*REQUEST_COLUMNS, "error_type", "outlier"]), metadata, pd.concat(metric_frames, ignore_index=True) if metric_frames else pd.DataFrame(), reports)
