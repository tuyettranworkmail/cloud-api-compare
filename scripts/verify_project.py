"""Run bounded project checks and write an auditable handover status."""
from __future__ import annotations

import json
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import nbformat

from benchmark.io import read_json, utcnow, write_json
from benchmark.runner import k6_binary


def main() -> int:
    reports = Path("reports")
    reports.mkdir(exist_ok=True)
    checks = {}
    for name, args in {
        "pytest": [sys.executable, "-m", "pytest", "-q", "--junitxml=reports/test_results.xml"],
        "ruff": [sys.executable, "-m", "ruff", "check", "benchmark", "scripts", "dashboard", "examples", "tests"],
        "configuration": [sys.executable, "-m", "benchmark.cli", "validate"],
        "dry_run": [sys.executable, "-m", "benchmark.cli", "run-all", "--dry-run", "--repeats", "5"],
    }.items():
        process = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=180)
        (reports / f"verification_{name}.log").write_text(process.stdout + process.stderr, encoding="utf-8")
        checks[name] = {"passed": process.returncode == 0, "exit_code": process.returncode, "log": f"reports/verification_{name}.log"}
        print(name, "PASS" if process.returncode == 0 else "FAIL", flush=True)
    tests = ET.parse(reports / "test_results.xml").getroot()
    suites = tests.findall("testsuite") if tests.tag == "testsuites" else [tests]
    total = sum(int(suite.attrib["tests"]) for suite in suites)
    failures = sum(int(suite.attrib.get("failures", 0)) + int(suite.attrib.get("errors", 0)) for suite in suites)
    notebook_path = Path("notebooks/benchmark_analysis.executed.ipynb")
    notebook_ok = False
    if notebook_path.exists():
        notebook = nbformat.read(notebook_path, as_version=4)
        notebook_ok = all(cell.execution_count is not None and not any(output.output_type == "error" for output in cell.outputs) for cell in notebook.cells if cell.cell_type == "code")
    summary_paths = list(Path("results/local_smoke").rglob("summary.json"))
    smoke_summaries = [(p, read_json(p)) for p in summary_paths if "jobs" in read_json(p)]
    smoke = max(smoke_summaries, key=lambda pair: pair[0].stat().st_mtime) if smoke_summaries else None
    demo = read_json(Path("demo_data/manifest.json"))
    figures = len(list(Path("charts/demo").rglob("*.png")))
    svg = len(list(Path("charts/demo").rglob("*.svg")))
    excel_path = Path("reports/generated/demo/benchmark_results_demo.xlsx")
    result = {"verified_at_utc": utcnow(), "user_timezone": "Asia/Saigon", "python": sys.version, "platform": platform.platform(), "k6": subprocess.check_output([k6_binary(), "version"], text=True).strip(), "checks": checks, "tests": total, "test_failures": failures, "notebook_executed": notebook_ok, "local_k6": {"all_passed": smoke[1]["all_passed"], "jobs": len(smoke[1]["jobs"]), "path": str(smoke[0])} if smoke else {"status": "NOT_EXECUTED"}, "demo_runs": demo["runs"], "demo_requests": demo["requests"], "figures_png": figures, "figures_svg": svg, "gcp_benchmark": "NOT_EXECUTED", "real_cloud_metrics_collection": "NOT_EXECUTED_REQUIRES_ADC_AND_RESOURCE_IDENTIFIERS", "real_api_contract_validation": "NOT_EXECUTED_REQUIRES_TARGET_URLS", "billing_invoice_reconciled": False, "excel_export": "IMPLEMENTED_OPENPYXL_USER_SELECTED" if excel_path.exists() else "MISSING", "all_local_checks_passed": all(c["passed"] for c in checks.values()) and notebook_ok and smoke is not None and smoke[1]["all_passed"] and figures == svg == 24 and excel_path.exists()}
    write_json(reports / "verification.json", result)
    text = f"""# Checklist bàn giao — Phúc Hoàng

Ngày bàn giao: 31/10/2026 (Asia/Saigon). Chi tiết timestamp UTC và phiên bản trong `verification.json`.

**Chưa chạy benchmark GCP thật. DEMO và LOCAL_TEST không là bằng chứng thực nghiệm GCP.**

| Thành phần | Trạng thái kiểm chứng | Lệnh / output |
|---|---|---|
| Source Python / config / CLI | {'PASS' if checks['configuration']['passed'] else 'FAIL'} | `python -m benchmark.cli validate` |
| Pytest | {total-failures}/{total} test không lỗi | `python -m pytest -q`; `reports/test_results.xml` |
| Ruff | {'PASS' if checks['ruff']['passed'] else 'FAIL'} | `python -m ruff check benchmark scripts dashboard examples tests` |
| k6 thực thi local | {len(smoke[1]['jobs']) if smoke else 0} jobs; {'PASS' if smoke and smoke[1]['all_passed'] else 'NOT EXECUTED'} | `python scripts/local_smoke.py`; `{smoke[0] if smoke else 'results/local_smoke/'}` |
| API equivalence local | PASS nếu local smoke passed | `results/local_smoke/compatibility.json` |
| DEMO tái lập | {demo['runs']} run / {demo['requests']} simulated requests | `python -m benchmark.cli demo --all`; `demo_data/` |
| Statistics / missing / zero / outlier / CI | Pytest + demo pipeline | `results/processed/demo/` |
| Cold/warm và scale-out | Module/test đã chạy; cold thiếu mẫu trả INSUFFICIENT_DATA | `cold_warm.csv`, `cold_penalty.csv`, `scaling.csv`, `burst_response.csv` |
| Chi phí / free tier / break-even / sensitivity | Module/test chạy; giá có nguồn, usage là giả định DEMO | `python -m benchmark.cli cost`; `results/financial/demo/` |
| PNG / SVG / HTML | {figures} PNG + {svg} SVG, HTML tương tác | `python -m benchmark.cli export`; `charts/demo/` |
| Notebook end-to-end | {'PASS' if notebook_ok else 'NOT EXECUTED'} | `python scripts/execute_notebook.py`; `notebooks/benchmark_analysis.executed.ipynb` |
| Dashboard | 8 trang được AppTest kiểm tra | `python -m streamlit run dashboard/app.py` |
| Decision engine | Tests + 8 case mô phỏng; REAL mặc định cần đủ evidence | `python -m benchmark.cli decision`; `reports/generated/demo/decision/` |
| Budget / dry-run | {'PASS' if checks['dry_run']['passed'] else 'FAIL'}; không liên hệ cloud | `python -m benchmark.cli run-all --dry-run` |
| Google Monitoring / Logging collector | Mã nguồn + mocked tests; chưa gọi cloud thật | Cần ADC, IAM và service/instance identifiers |
| Runtime resource snapshot / Docker inspection | Có code đọc; chưa chạy GCP | Cần quyền viewer/SSH và resource names đúng |
| Live contract của nhóm | CHƯA THỰC HIỆN | Cần ba URL và auth; `validate --live` |
| Benchmark REAL / confirmed cloud cold / cloud scaling | CHƯA THỰC HIỆN | Cần GCP load VM, quota, budget bounds, API URLs và resources |
| Invoice reconciliation | CHƯA THỰC HIỆN | Cần usage/Billing export thật, đúng tháng/volume |
| Excel .xlsx | openpyxl theo lựa chọn người dùng; công thức/biểu đồ native/source URLs | `reports/generated/demo/benchmark_results_demo.xlsx`; QA riêng trong `excel_native_verification.json` |
| Linux execution | Code/commands hỗ trợ; chưa thực thi tại phiên bàn giao Windows | Chạy lại tests/local_smoke trên VM Linux trước đo chính thức |

## Đầu vào còn cần từ nhóm

- URL/auth/OpenAPI thật; mapping/schema và seed IDs tồn tại trong Firestore asia-southeast1.
- VM name/ID/zone, Cloud Run services và function GEN_2 name; config CPU/RAM/concurrency/timeout/billing và worker evidence.
- ADC/IAM đọc Monitoring/config; Logging nếu cần; Docker evidence từ chủ IaaS cho controlled mode.
- Pilot capacity của IaaS tại SLA; kiểm chứng VM tạo tải cùng region và không là bottleneck.
- Conservative price bounds/quota review và kế hoạch trong budget; usage/profile/means thật để thay giả định DEMO.

## Lệnh tái lập ngay

```powershell
.venv\\Scripts\\python.exe -m benchmark.cli demo --all
.venv\\Scripts\\python.exe scripts/execute_notebook.py
.venv\\Scripts\\python.exe -m streamlit run dashboard/app.py
```

Không có tài nguyên GCP được toolkit tạo/xóa trong quá trình bàn giao. Không có số liệu giả được gắn nhãn REAL.
"""
    (reports / "handover_checklist.md").write_text(text, encoding="utf-8")
    print(json.dumps({"all_local_checks_passed": result["all_local_checks_passed"], "tests": total, "notebook_executed": notebook_ok}))
    return 0 if result["all_local_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
