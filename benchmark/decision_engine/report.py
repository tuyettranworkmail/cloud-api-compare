from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import yaml

from benchmark.decision_engine.engine import Workload, recommend
from benchmark.io import DEMO_LABEL, write_json

MERMAID = """flowchart TD
    A[Workload + SLA + control + budget] --> B{Representative REAL evidence?}
    B -->|No| X[INCONCLUSIVE]
    B -->|Yes| C[Filter security / OS control / operations / portability]
    C --> D[Filter duration / background / cold tolerance]
    D --> E[Filter run CI / error rate / peak capacity]
    E --> F{Any candidates within budget?}
    F -->|No| X
    F -->|Yes| G[Compare estimated full cost + sensitivity]
    G --> H{Equal suitable costs?}
    H -->|Yes| I[Use workload preferences or INCONCLUSIVE]
    H -->|No| J[Recommend lowest-cost eligible configuration]
"""


def case_studies(output: Path, policy_path=Path("configs/decision_policy.yaml")) -> list[dict]:
    policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=True)
    # These explicit synthetic decision fixtures exercise the algorithm; they are
    # deliberately separate from measured/observed repository performance tables.
    evidence = {model: {"data_mode": "DEMO", "number_of_runs": 5, "p95_ci_upper_ms": 100, "achieved_rps": 100, "error_rate_pct": .1, "cold_p95_ms": 900 if model != "iaas" else 100, "monthly_cost_usd": 70 if model == "iaas" else 20, "capacity_supported": True} for model in ("iaas", "paas", "faas")}
    base = Workload(100000, .05, 2, .6, 200, None, "standard", "high", False, "medium", 100, 20, evidence_scope_verified=True)
    cases = [
        ("API container cần portability cao", replace(base, portability="high")),
        ("Sự kiện gián đoạn", replace(base, event_driven=True)),
        ("Cần quyền OS", replace(base, required_control="os")),
        ("Cold SLA nghiêm ngặt", replace(base, cold_tolerance_ms=150)),
        ("Peak vượt phạm vi đã đo", replace(base, peak_rps=1000, burstiness=20)),
        ("Background lâu, chưa xác minh timeout", replace(base, long_running_background=True, average_duration_seconds=7200)),
        ("Không đủ ngân sách", replace(base, budget_usd=1)),
        ("Chưa có dữ liệu thật", replace(base, evidence_scope_verified=False)),
    ]
    results = [{"case": title, "label": DEMO_LABEL, "result": recommend(workload, evidence, policy, allow_demo=True)} for title, workload in cases]
    write_json(output / "case_studies.json", results)
    (output / "decision_tree.mmd").write_text(MERMAID, encoding="utf-8")
    return results
