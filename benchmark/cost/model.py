"""Auditable estimates. This model never claims to be a Cloud Billing invoice."""
from __future__ import annotations

import copy
import math
from pathlib import Path

import numpy as np
import yaml
from scipy.stats import poisson


class PriceMissingError(ValueError):
    pass


class CostModel:
    def __init__(self, catalog: dict, workload: dict):
        self.catalog = copy.deepcopy(catalog)
        self.workload = copy.deepcopy(workload)
        if catalog["currency"] != "USD" or catalog["region"] != "asia-southeast1":
            raise ValueError("Catalog cần USD / asia-southeast1")
        self.validate()

    @classmethod
    def from_files(cls, catalog=Path("configs/pricing_catalog.yaml"), workload=Path("configs/cost_workloads.yaml")):
        return cls(yaml.safe_load(catalog.read_text(encoding="utf-8")), yaml.safe_load(workload.read_text(encoding="utf-8")))

    def validate(self):
        a = self.workload["assumptions"]
        if self.workload["data_mode"] not in {"DEMO", "REAL"}:
            raise ValueError("Cost data_mode phải là DEMO hoặc REAL")
        for key, value in a.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool) and (not math.isfinite(value) or value < 0):
                raise ValueError(f"Giả định {key} phải hữu hạn, không âm")
        if not 0 <= a["internet_egress_fraction"] <= 1:
            raise ValueError("internet_egress_fraction phải từ 0 đến 1")
        if any(v < 0 for v in a["mix"].values()) or abs(sum(a["mix"].values()) - 1) > 1e-9:
            raise ValueError("mix phải có tổng 1 và không âm")
        if not 0 < a["active_hours_per_day"] <= 24 or not 0 <= a["idle_ratio"] < 1:
            raise ValueError("Traffic profile không hợp lệ")
        if a["days"] < 1 or int(a["days"]) != a["days"] or a["vm_hours"] < 0 or a["peak_to_average"] < 1:
            raise ValueError("Workload duration/peak không hợp lệ")
        if a["free_tier"] and (not a["free_tier_eligible"] or a["free_tier_scope"] != "mutually_exclusive_alternatives"):
            raise ValueError("Free tier cần xác minh điều kiện và phạm vi billing account")
        if not 0 <= a["free_tier_remaining_fraction"] <= 1:
            raise ValueError("Remaining free credit phải từ 0 đến 1")
        for model in ("paas", "faas"):
            m = self.workload["models"][model]
            for key, value in m.items():
                if isinstance(value, (int, float)) and (not math.isfinite(value) or value < 0):
                    raise ValueError(f"{model}.{key} phải hữu hạn, không âm")
            if m["billing_mode"] not in {"request", "instance"} or m["vcpu"] <= 0 or m["memory_gib"] <= 0 or m["concurrency"] < 1 or not 0 < m["target_cpu_utilization"] <= 1 or m["min_instances"] < 0 or m["max_instances"] < max(1, m["min_instances"]):
                raise ValueError("Serverless allocation không hợp lệ")
        for name in ("mean_duration_seconds", "mean_cpu_seconds"):
            if set(a[name]) != set(a["mix"]) or any(v < 0 for v in a[name].values()):
                raise ValueError("Endpoint durations phải đủ và không âm")

    def price(self, key: str, quantity: float) -> float:
        if quantity < 0 or not math.isfinite(quantity):
            raise ValueError("Quantity phải hữu hạn và không âm")
        if quantity == 0:
            return 0.0
        rate = self.catalog["rates"][key]
        if rate["unit_price"] is None:
            raise PriceMissingError(f"Thiếu giá {key}: cập nhật từ {rate['source']}; không được tự điền 0")
        if not math.isfinite(rate["unit_price"]) or rate["unit_price"] < 0 or not rate.get("source"):
            raise ValueError(f"Giá {key} cần hữu hạn, không âm và có nguồn")
        return quantity * rate["unit_price"] * self.workload["assumptions"]["price_multiplier"]

    def profile(self, requests: float) -> tuple[np.ndarray, np.ndarray]:
        """Representative hourly bins over a billing month (not observed traffic)."""
        a = self.workload["assumptions"]
        bins = max(24, math.ceil(a["days"] * 24))
        weights = np.ones(bins)
        if a["distribution"] == "business":
            weights = ((np.arange(bins) % 24) < a["active_hours_per_day"]).astype(float)
        elif a["distribution"] == "bursty":
            active_fraction = 1 - a["idle_ratio"]
            weights = ((np.arange(bins) % 24) < max(1, math.ceil(24 * active_fraction))).astype(float)
            active_indices = np.flatnonzero(weights)
            weights[active_indices[::max(1, math.ceil(a["peak_to_average"]))]] *= a["peak_to_average"]
        elif a["distribution"] != "uniform":
            raise ValueError("distribution phải là uniform/business/bursty")
        # Include peak-to-average effect also for non-bursty profiles.
        if a["distribution"] != "bursty" and a["peak_to_average"] > 1:
            weights[np.flatnonzero(weights)[::24]] *= a["peak_to_average"]
        seconds = np.full(bins, a["days"] * 86400 / bins)
        arrivals = requests * weights / weights.sum()
        return arrivals / seconds, seconds

    def estimate(self, model: str, requests: float) -> dict:
        self.validate()
        if not math.isfinite(requests) or requests < 0:
            raise ValueError("Monthly requests phải hữu hạn và không âm")
        a, m, free = self.workload["assumptions"], self.workload["models"][model], self.catalog["free_tier"]
        rps, seconds = self.profile(requests)
        use_free = a["free_tier"]
        remaining = a["free_tier_remaining_fraction"]
        breakdown = {}
        warnings = ["ESTIMATE_ONLY: mean service/CPU demand, traffic profile and overlap assumptions must be calibrated"]
        # Daily Firestore quota: aggregate actual daily demand BEFORE applying allowance.
        daily_requests = (rps * seconds).reshape(-1, 24).sum(axis=1)
        fs_free = use_free and a["firestore_free_eligible"]
        retries = m.get("firestore_retry_multiplier", a["firestore_retry_multiplier"])
        reads = daily_requests * a["mix"]["read"] * (a["firestore_reads_per_get"] + a["firestore_index_read_batches_per_get"]) * retries
        writes = daily_requests * a["mix"]["write"] * a["firestore_writes_per_post"] * retries
        deletes = daily_requests * a["firestore_deletes_per_request"]
        for name, operations, allowance in (("read", reads, free["firestore_reads_per_day"]), ("write", writes, free["firestore_writes_per_day"]), ("delete", deletes, free["firestore_deletes_per_day"])):
            billable = float(np.maximum(operations - (allowance * remaining if fs_free else 0), 0).sum())
            breakdown[f"firestore_{name}"] = self.price(f"firestore_{name}", billable)
        breakdown["firestore_storage"] = self.price("firestore_storage", max(0, a["firestore_storage_gib"] - (free["firestore_storage_gib"] * remaining if fs_free else 0)))
        breakdown["firestore_network_optional"] = a["firestore_network_usd"] + a["firestore_optional_usd"]
        breakdown["network"] = self.price("egress_gib", requests * a["response_bytes"] / 2**30 * a["internet_egress_fraction"])
        breakdown["logging"] = self.price("logging_gib", a["logging_gib"])
        breakdown["monitoring"] = self.price("monitoring_mib", a["monitoring_mib"])
        breakdown["build"] = self.price("build_minute", a["build_minutes"])
        breakdown["artifact"] = self.price("artifact_gib_month", a["artifact_gib"])
        breakdown["backup_auxiliary"] = a["backup_usd"] + a["auxiliary_usd"]
        breakdown["labor"] = a["labor_usd_per_hour"] * m["labor_hours"]
        capacity_status = "UNVERIFIED"
        active = lifetime = idle = np.nan
        mean_wall = sum(a["mix"][ep] * a["mean_duration_seconds"][ep] for ep in a["mix"])
        mean_cpu = sum(a["mix"][ep] * a["mean_cpu_seconds"][ep] for ep in a["mix"])
        if model == "iaas":
            breakdown["compute"] = self.price("vm_hour", a["vm_hours"] * m["vm_count"])
            breakdown["disk"] = self.price("disk_gib_month", a["disk_gib"] * m["vm_count"])
            breakdown["external_ip"] = self.price("ipv4_hour", a["external_ipv4_count"] * a["vm_hours"])
            if m["capacity_rps"] is None:
                warnings.append("IaaS capacity chưa đo: chi phí một VM không chứng minh VM đáp ứng tải")
            else:
                capacity_status = "SUPPORTED" if float(rps.max()) <= m["capacity_rps"] * m["vm_count"] else "UNSUPPORTED_CAPACITY"
            method = "fixed VM, full host billing independent of app container limits"
        else:
            # Poisson occupancy with perfect request packing is an explicit estimation assumption.
            # Never divide all request time by configured concurrency at sparse traffic.
            rounded_wall = math.ceil(mean_wall / .1) * .1 if mean_wall else 0
            occupancy = rps * rounded_wall
            # E[ceil(X/c)] = sum_k P(X > k*c), X ~ Poisson(offered load).
            unique, inverse = np.unique(occupancy, return_inverse=True)
            terms = max(1, min(1000, math.ceil(float(unique.max()) / m["concurrency"] + 10)))
            expected = poisson.sf(np.arange(terms)[:, None] * m["concurrency"], unique[None, :]).sum(axis=0)
            effective = expected[inverse]
            cpu_floor = rps * mean_cpu / (m["vcpu"] * m["target_cpu_utilization"])
            busy_instances = np.maximum(effective, cpu_floor)
            needed_peak = max(float(np.ceil(busy_instances.max())), float(np.ceil((rps * mean_wall / m["concurrency"]).max())))
            capacity_status = "ESTIMATED_SUPPORTED" if needed_peak <= m["max_instances"] else "UNSUPPORTED_CAPACITY"
            startup = m["startup_count"] * math.ceil((m["startup_seconds"] + m["shutdown_seconds"]) / .1) * .1
            if requests == 0 and m["min_instances"] == 0:
                startup = 0
            active = float(np.dot(busy_instances, seconds)) + startup
            idle = float(np.dot(np.maximum(m["min_instances"] - busy_instances, 0), seconds))
            # Conservative hourly provisioning and scale-down tails for instance billing.
            provisioned = np.maximum(np.ceil(busy_instances), m["min_instances"])
            lifetime = float(np.dot(provisioned, seconds)) + startup + m["startup_count"] * m["scale_down_tail_seconds"] if requests else float(m["min_instances"] * seconds.sum())
            lifetime = max(lifetime, m["startup_count"] * 60 if requests else lifetime)
            method = "estimated hourly Poisson occupancy + CPU floor; 100 ms rounded mean; startup and scale-down assumptions"
            if m["measured_active_instance_seconds"] is not None:
                active = float(m["measured_active_instance_seconds"])
                method = "measured active instance-seconds for exactly this monthly traffic; not automatically scaled"
                warnings.append("Measured instance-seconds must cover this exact month/volume; free-tier/idle billed separately")
            if m["measured_lifetime_instance_seconds"] is not None:
                lifetime = float(m["measured_lifetime_instance_seconds"])
            if m["billing_mode"] == "request":
                cpu_cost = self.price("run_cpu_request", active * m["vcpu"])
                mem_cost = self.price("run_memory_request", active * m["memory_gib"])
                cpu_idle = self.price("run_cpu_idle", idle * m["vcpu"])
                mem_idle = self.price("run_memory_idle", idle * m["memory_gib"])
                breakdown["compute_cpu"] = max(0, cpu_cost + cpu_idle - (free["request_cpu_credit_usd"] * remaining if use_free else 0))
                breakdown["compute_memory"] = max(0, mem_cost + mem_idle - (free["request_memory_credit_usd"] * remaining if use_free else 0))
                breakdown["requests"] = self.price("run_request", max(0, requests - (free["requests"] * remaining if use_free else 0)))
            else:
                breakdown["compute_cpu"] = max(0, self.price("run_cpu_instance", lifetime * m["vcpu"]) - (free["instance_cpu_credit_usd"] * remaining if use_free else 0))
                breakdown["compute_memory"] = max(0, self.price("run_memory_instance", lifetime * m["memory_gib"]) - (free["instance_memory_credit_usd"] * remaining if use_free else 0))
                breakdown["requests"] = 0.0
        shared = sum(v for k, v in breakdown.items() if k.startswith("firestore"))
        compute = sum(v for k, v in breakdown.items() if k.startswith("compute"))
        total = sum(breakdown.values())
        if capacity_status == "UNSUPPORTED_CAPACITY":
            warnings.append("Configuration không đáp ứng peak demand; tổng này không phải giá của workload được đáp ứng")
        return {"model": model, "monthly_requests": requests, "data_mode": self.workload["data_mode"], "currency": "USD", "total_usd": total, "compute_usd": compute, "shared_data_usd": shared, "without_shared_usd": total - shared, "cost_per_million_usd": total / requests * 1e6 if requests else None, "peak_rps": float(rps.max()), "capacity_status": capacity_status, "billable_active_instance_seconds": active, "estimated_lifetime_instance_seconds": lifetime, "idle_instance_seconds": idle, "method": method, "warnings": warnings, "breakdown": breakdown}
