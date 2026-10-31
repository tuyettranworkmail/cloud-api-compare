# Checklist bàn giao — Phúc Hoàng

Ngày bàn giao: 31/10/2026 (Asia/Saigon). Chi tiết timestamp UTC và phiên bản trong `verification.json`.

**Chưa chạy benchmark GCP thật. DEMO và LOCAL_TEST không là bằng chứng thực nghiệm GCP.**

| Thành phần | Trạng thái kiểm chứng | Lệnh / output |
|---|---|---|
| Source Python / config / CLI | PASS | `python -m benchmark.cli validate` |
| Pytest | 71/71 test không lỗi | `python -m pytest -q`; `reports/test_results.xml` |
| Ruff | PASS | `python -m ruff check benchmark scripts dashboard examples tests` |
| k6 thực thi local | 12 jobs; PASS | `python scripts/local_smoke.py`; `results\local_smoke\2026-10-31T04-14-08.045095+00-00\summary.json` |
| API equivalence local | PASS nếu local smoke passed | `results/local_smoke/compatibility.json` |
| DEMO tái lập | 75 run / 36840 simulated requests | `python -m benchmark.cli demo --all`; `demo_data/` |
| Statistics / missing / zero / outlier / CI | Pytest + demo pipeline | `results/processed/demo/` |
| Cold/warm và scale-out | Module/test đã chạy; cold thiếu mẫu trả INSUFFICIENT_DATA | `cold_warm.csv`, `cold_penalty.csv`, `scaling.csv`, `burst_response.csv` |
| Chi phí / free tier / break-even / sensitivity | Module/test chạy; giá có nguồn, usage là giả định DEMO | `python -m benchmark.cli cost`; `results/financial/demo/` |
| PNG / SVG / HTML | 24 PNG + 24 SVG, HTML tương tác | `python -m benchmark.cli export`; `charts/demo/` |
| Notebook end-to-end | PASS | `python scripts/execute_notebook.py`; `notebooks/benchmark_analysis.executed.ipynb` |
| Dashboard | 8 trang được AppTest kiểm tra | `python -m streamlit run dashboard/app.py` |
| Decision engine | Tests + 8 case mô phỏng; REAL mặc định cần đủ evidence | `python -m benchmark.cli decision`; `reports/generated/demo/decision/` |
| Budget / dry-run | PASS; không liên hệ cloud | `python -m benchmark.cli run-all --dry-run` |
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
.venv\Scripts\python.exe -m benchmark.cli demo --all
.venv\Scripts\python.exe scripts/execute_notebook.py
.venv\Scripts\python.exe -m streamlit run dashboard/app.py
```

Không có tài nguyên GCP được toolkit tạo/xóa trong quá trình bàn giao. Không có số liệu giả được gắn nhãn REAL.
