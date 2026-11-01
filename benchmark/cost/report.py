from __future__ import annotations

import copy
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from benchmark.cost.breakeven import find_intersections
from benchmark.cost.model import CostModel
from benchmark.io import write_json


def sensitivity(model: CostModel, volume=2_000_000) -> pd.DataFrame:
    rows = []
    # Each variation recomputes the full model, including traffic/capacity assumptions.
    parameters = ["monthly_requests", "cpu_execution_time", "memory_gib", "read_ratio", "response_bytes", "concurrency", "peak_to_average", "active_hours_per_day", "min_instances", "price_multiplier", "labor_usd_per_hour"]
    for deployment in model.workload["models"]:
        base = model.estimate(deployment, volume)["total_usd"]
        for parameter in parameters:
            for direction, factor in (("low", .5), ("high", 1.5)):
                other = CostModel(model.catalog, model.workload)
                a = other.workload["assumptions"]
                m = other.workload["models"][deployment]
                n = volume
                if parameter == "monthly_requests":
                    n *= factor
                elif parameter == "cpu_execution_time":
                    a["mean_cpu_seconds"] = {k: v * factor for k, v in a["mean_cpu_seconds"].items()}
                elif parameter == "memory_gib" and deployment != "iaas":
                    m["memory_gib"] *= factor
                elif parameter == "concurrency" and deployment != "iaas":
                    m["concurrency"] = max(1, round(m["concurrency"] * factor))
                elif parameter == "min_instances" and deployment != "iaas":
                    m["min_instances"] = 0 if direction == "low" else max(1, m["min_instances"] + 1)
                elif parameter == "read_ratio":
                    read = min(.95, a["mix"]["read"] * factor)
                    remainder = 1 - a["mix"]["read"]
                    if remainder > 0:
                        a["mix"] = {"read": read, **{k: (1 - read) * v / remainder for k, v in a["mix"].items() if k != "read"}}
                    else:
                        # At an all-read boundary, keep the original mix rather than
                        # inventing a POST/CPU allocation for the sensitivity scenario.
                        a["mix"] = dict(a["mix"])
                elif parameter == "labor_usd_per_hour":
                    a[parameter] = 0 if direction == "low" else max(10, a[parameter] * factor)
                elif parameter == "active_hours_per_day":
                    a["distribution"] = "business"
                    a[parameter] = min(24, max(1, a[parameter] * factor))
                elif parameter in a:
                    a[parameter] = max(1, a[parameter] * factor) if parameter == "peak_to_average" else a[parameter] * factor
                result = other.estimate(deployment, n)
                rows.append({"data_mode": model.workload["data_mode"], "model": deployment, "parameter": parameter, "direction": direction, "base_usd": base, "total_usd": result["total_usd"], "delta_usd": result["total_usd"] - base, "capacity_status": result["capacity_status"], "note": "IaaS memory/concurrency change needs a separately priced VM/config" if deployment == "iaas" and parameter in {"memory_gib", "concurrency", "min_instances"} else ""})
    return pd.DataFrame(rows)


def cost_report(model: CostModel, output: Path, *, maximum_requests=1e9, grid_size=121) -> dict[str, pd.DataFrame]:
    output.mkdir(parents=True, exist_ok=True)
    workload = copy.deepcopy(model.workload)
    if any(workload["models"][m].get("measured_active_instance_seconds") is not None or workload["models"][m].get("measured_lifetime_instance_seconds") is not None for m in ("paas", "faas")):
        raise ValueError("Traffic curves/sensitivity không được dùng fixed measured seconds cho nhiều N; cấu hình estimator hoặc model theo từng volume")
    rows, breakdown = [], []
    for level, volume in workload["traffic_levels"].items():
        for deployment in workload["models"]:
            result = model.estimate(deployment, volume)
            components = result.pop("breakdown")
            result["warnings"] = "; ".join(result["warnings"])
            rows.append({"level": level, **result})
            breakdown.extend({"level": level, "data_mode": workload["data_mode"], "model": deployment, "component": component, "usd": amount} for component, amount in components.items())
    curve = []
    cache = {}

    def estimate(deployment, n):
        key = (deployment, float(n))
        if key not in cache:
            cache[key] = model.estimate(deployment, n)
        return cache[key]

    for n in np.geomspace(1, maximum_requests, grid_size):
        for deployment in workload["models"]:
            value = estimate(deployment, float(n))
            curve.append({"data_mode": workload["data_mode"], "model": deployment, "monthly_requests": n, "total_usd": value["total_usd"], "cost_per_million_usd": value["cost_per_million_usd"], "capacity_status": value["capacity_status"]})
    intersections = []
    for left, right in combinations(workload["models"], 2):
        result = find_intersections(lambda n: estimate(left, n)["total_usd"], lambda n: estimate(right, n)["total_usd"], 0, maximum_requests, grid_size=grid_size)
        roots = [{"requests": n, "cost_usd": estimate(left, n)["total_usd"], "left_capacity": estimate(left, n)["capacity_status"], "right_capacity": estimate(right, n)["capacity_status"], "operationally_feasible": estimate(left, n)["capacity_status"] in {"SUPPORTED", "ESTIMATED_SUPPORTED"} and estimate(right, n)["capacity_status"] in {"SUPPORTED", "ESTIMATED_SUPPORTED"}} for n in result["roots"]]
        intersections.append({"left": left, "right": right, **result, "root_details": roots, "interpretation": "financial intersections only; feasible only when both capacity/SLA validated"})
    tables = {"cost_levels": pd.DataFrame(rows), "cost_breakdown": pd.DataFrame(breakdown), "cost_curve": pd.DataFrame(curve), "sensitivity": sensitivity(model)}
    for name, table in tables.items():
        table.to_csv(output / f"{name}.csv", index=False, encoding="utf-8-sig")
    write_json(output / "break_even.json", intersections)
    write_json(output / "pricing_catalog.json", model.catalog)
    write_json(output / "workload_assumptions.json", workload)
    write_json(output / "cost_status.json", {"status": "ESTIMATED", "data_mode": workload["data_mode"], "missing_unused_prices": [k for k, v in model.catalog["rates"].items() if v["unit_price"] is None], "real_billing_validated": False})
    return tables
