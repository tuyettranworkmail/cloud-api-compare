from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from benchmark.config import ConfigError, load_config
from benchmark.io import serializable, write_json


def main(argv=None) -> int:
    # Windows PowerShell pipes otherwise use a legacy console codepage.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Phúc Hoàng • Benchmark + chi phí + phân tích")
    parser.add_argument("--config-dir", type=Path, default=Path(os.environ.get("BENCH_CONFIG_DIR", "configs")))
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="Validate local config and optionally live contracts")
    validate.add_argument("--live", action="store_true")
    validate.add_argument("--output", type=Path, default=Path("results/compatibility.json"))
    for name in ("run", "run-all"):
        run = sub.add_parser(name)
        run.add_argument("--scenario", choices=["steady", "burst", "idle"], default="steady" if name == "run" else None)
        run.add_argument("--target", choices=["iaas", "paas", "faas"], default="iaas" if name == "run" else None)
        run.add_argument("--level", choices=["low", "medium", "high"], default="medium" if name == "run" else None)
        run.add_argument("--endpoint", choices=["read", "write", "cpu"])
        run.add_argument("--repeats", type=int)
        run.add_argument("--dry-run", action="store_true")
        run.add_argument("--resume", action="store_true")
        run.add_argument("--output", type=Path, default=Path("results"))
    demo = sub.add_parser("demo")
    demo.add_argument("--output", type=Path, default=Path("demo_data"))
    demo.add_argument("--seed", type=int, default=20261031)
    demo.add_argument("--repeats", type=int, default=5)
    demo.add_argument("--all", action="store_true", help="Generate, analyze, cost, charts, research report")
    analysis = sub.add_parser("analyze")
    analysis.add_argument("--input", type=Path, default=Path("demo_data"))
    analysis.add_argument("--output", type=Path, default=Path("results/processed/demo"))
    analysis.add_argument("--bootstrap", type=int)
    cost = sub.add_parser("cost")
    cost.add_argument("--catalog", type=Path)
    cost.add_argument("--workload", type=Path)
    cost.add_argument("--output", type=Path, default=Path("results/financial/demo"))
    cost.add_argument("--max-requests", type=float, default=1e9)
    export = sub.add_parser("export")
    export.add_argument("--analysis", type=Path, default=Path("results/processed/demo"))
    export.add_argument("--financial", type=Path, default=Path("results/financial/demo"))
    export.add_argument("--output", type=Path, default=Path("charts/demo"))
    export.add_argument("--reports", type=Path, default=Path("reports/generated/demo"))
    export.add_argument("--sla-ms", type=float, default=500)
    collect = sub.add_parser("collect")
    collect.add_argument("--target", choices=["iaas", "paas", "faas"], required=True)
    collect.add_argument("--start", required=True)
    collect.add_argument("--end", required=True)
    collect.add_argument("--output", type=Path, required=True)
    decision = sub.add_parser("decision")
    decision.add_argument("--output", type=Path, default=Path("reports/decision"))
    decision.add_argument("--workload", type=Path)
    decision.add_argument("--evidence", type=Path)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        c = load_config(args.config_dir)
        result = {}
        if args.command == "validate":
            if args.live:
                from benchmark.validators import validate_contracts
                result = validate_contracts(c, allow_writes=c["experiments"]["safety"]["allow_benchmark_writes"])
                write_json(args.output, result)
                if not result["passed"]:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                    return 2
            else:
                result = {"local_config": "PASS", "live_contracts": "NOT_EXECUTED", "cloud_benchmark": "NOT_EXECUTED"}
        elif args.command in {"run", "run-all"}:
            from benchmark.runner import execute_plan, plan_experiments
            plan = plan_experiments(c, scenarios=[args.scenario] if args.scenario else None, models=[args.target] if args.target else None, levels=[args.level] if args.level else None, repeats=args.repeats, endpoint=args.endpoint)
            result = execute_plan(c, plan, args.output, dry_run=args.dry_run, resume=args.resume)
            if not args.dry_run and (result["remaining_not_started"] or any(r["status"] != "COMPLETE" for r in result["runs"])):
                print(json.dumps(serializable(result), ensure_ascii=False, indent=2))
                return 2
        elif args.command == "demo":
            from benchmark.demo import generate_demo
            result = generate_demo(c, args.output, args.seed, args.repeats)
            if args.all:
                from benchmark.cost.model import CostModel
                from benchmark.cost.report import cost_report
                from benchmark.reporting import build_research_report
                from benchmark.statistics import analyze
                from benchmark.visualization.charts import export_charts
                analysis_dir, finance_dir = Path("results/processed/demo"), Path("results/financial/demo")
                analyze(args.output, analysis_dir, resamples=c["experiments"]["bootstrap_resamples"], minimum_samples=c["experiments"]["minimum_samples"])
                cost_report(CostModel.from_files(args.config_dir / "pricing_catalog.yaml", args.config_dir / "cost_workloads.yaml"), finance_dir)
                export_charts(analysis_dir, finance_dir, Path("charts/demo"))
                build_research_report(analysis_dir, finance_dir, Path("reports/generated/demo"))
        elif args.command == "analyze":
            from benchmark.statistics import analyze
            tables = analyze(args.input, args.output, resamples=args.bootstrap or c["experiments"]["bootstrap_resamples"], minimum_samples=c["experiments"]["minimum_samples"])
            result = {name: len(frame) for name, frame in tables.items()}
        elif args.command == "cost":
            from benchmark.cost.model import CostModel
            from benchmark.cost.report import cost_report
            model = CostModel.from_files(args.catalog or args.config_dir / "pricing_catalog.yaml", args.workload or args.config_dir / "cost_workloads.yaml")
            result = {name: len(frame) for name, frame in cost_report(model, args.output, maximum_requests=args.max_requests).items()}
        elif args.command == "export":
            from benchmark.reporting import build_research_report
            from benchmark.visualization.charts import export_charts
            manifest = export_charts(args.analysis, args.financial, args.output, args.sla_ms)
            build_research_report(args.analysis, args.financial, args.reports)
            result = {"figures": len(manifest), "directory": str(args.output)}
        elif args.command == "collect":
            from benchmark.collectors.gcp import collect_metrics
            result = collect_metrics(c, args.target, args.start, args.end, args.output)["metric_status"]
        elif args.command == "decision":
            from benchmark.decision_engine.report import case_studies
            if args.workload and args.evidence:
                import yaml
                from benchmark.decision_engine import Workload, recommend
                from benchmark.io import read_json
                result = recommend(Workload(**read_json(args.workload)), read_json(args.evidence), yaml.safe_load((args.config_dir / "decision_policy.yaml").read_text(encoding="utf-8")))
                write_json(args.output / "recommendation.json", result)
            elif args.workload or args.evidence:
                raise ConfigError("Cần cả --workload và --evidence")
            else:
                result = {"demo_cases": len(case_studies(args.output, args.config_dir / "decision_policy.yaml"))}
        print(json.dumps(serializable(result), ensure_ascii=False, indent=2))
        return 0
    except (ValueError, FileNotFoundError, RuntimeError, OSError) as error:
        logging.error("%s: %s", type(error).__name__, error)
        return 2
    except Exception as error:
        logging.error("%s: thao tác thất bại; kiểm tra credentials/config, không ghi nội dung token hoặc response", type(error).__name__)
        return 2


if __name__ == "__main__":
    sys.exit(main())
