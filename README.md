# Phúc Hoàng — Benchmark + Chi phí + Phân tích

Bộ công cụ Python 3.12/k6 cho đề tài **So sánh thực nghiệm IaaS, PaaS và FaaS cho cùng dịch vụ API**. Chỉ triển khai phần benchmark, đo đạc, thống kê, FinOps và trực quan hóa; không tạo hay thay thế hạ tầng của Tuyết Trân và Lộc.

**Dữ liệu đi kèm: SIMULATED DATA – NOT REAL CLOUD MEASUREMENTS. Chưa chạy benchmark trên GCP thật.** Các phép đo local trong `results/local_smoke/` cũng được gắn `LOCAL_TEST`, không phải số đo GCP.

## Chạy ngay trên Windows

Mở PowerShell tại thư mục dự án. Máy hiện tại đã có `.venv` Python 3.12 và k6 trong `.tools/`.

```powershell
.venv\Scripts\python.exe -m benchmark.cli validate
.venv\Scripts\python.exe -m benchmark.cli demo --all
.venv\Scripts\python.exe scripts/execute_notebook.py
.venv\Scripts\python.exe -m streamlit run dashboard/app.py
```

Dashboard mặc định mở `http://localhost:8501`. Dừng bằng Ctrl+C. Chỉ là ứng dụng local; không có thao tác publish.

## Cài từ đầu

Cần Python **3.12**, pip/venv, Git; k6 được kiểm thử với **v2.3.0**. Python 3.12 có thể cài từ [python.org](https://www.python.org/downloads/) hoặc qua `uv python install 3.12`. Trên Windows nên bật “Add Python to PATH”.

Windows:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe scripts/install_k6.py --version v2.3.0
Copy-Item .env.example .env
```

Linux, trên **VM tạo tải riêng cùng region asia-southeast1**:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/install_k6.py --version v2.3.0
cp .env.example .env
```

Các lệnh còn lại dùng `python` sau khi activate venv (`.venv\Scripts\Activate.ps1` / `source .venv/bin/activate`), hoặc dùng đường dẫn Python tương ứng. Nếu PowerShell chặn activation, dùng trực tiếp `.venv\Scripts\python.exe`; không cần thay execution policy.

`scripts/install_k6.py` tải bản phát hành chính thức từ Grafana/GitHub, kiểm tra SHA256 và chỉ lưu binary trong `.tools/`. Có thể tự cài k6 theo [Grafana](https://grafana.com/docs/k6/latest/set-up/install-k6/). Đặt `K6_BIN` trong `.env` nếu cài ở vị trí khác. Không cần Docker cho toolkit.

Excel export dùng `openpyxl` theo lựa chọn của người dùng. Trên Windows có Microsoft Excel, có thể kiểm chứng native recalculation/preview bằng `.\scripts\recalculate_excel.ps1` rồi `python scripts/check_excel_cache.py`. Các bước COM này là QA tùy chọn; pipeline tạo `.xlsx` trên Windows/Linux không yêu cầu Excel. Bản bàn giao đã được tính lại và đối soát bằng Excel trên máy này.

`requirements-lock.txt` ghi phiên bản thư viện đã dùng để kiểm chứng. Để tái lập sát hơn, cài lock trước rồi `pip install -e . --no-deps`; wheel/phụ thuộc đặc thù OS có thể khác. Kiểm tra lại trên Linux trước phép đo chính thức; phiên bàn giao được thực thi trên Windows.

## Những gì đã có

| Thành phần | Mã nguồn / output |
|---|---|
| Cấu hình ba deployment, endpoint mapping, mix, trần tải | `configs/`, `.env.example` |
| Constant/ramping arrival rate; idle ở cấp runner | `k6/`, `benchmark/runner.py` |
| Preflight hợp đồng OpenAPI/schema/payload/CPU | `benchmark/validators.py` |
| Monitoring, logs, cấu hình GCP thực tế | `benchmark/collectors/gcp.py` |
| JSONL/CSV ingestion, missing/duplicate/outlier | `benchmark/parsers/` |
| Percentile, throughput, lỗi, CI theo run | `benchmark/statistics/` |
| Cold/warm, scale-out theo khoảng, burst stages | `benchmark/scaling/` |
| Chi phí, free tier, capacity, break-even, sensitivity | `benchmark/cost/` |
| 24 hình PNG 300 DPI + SVG + HTML tương tác | `charts/demo/` |
| Notebook tiếng Việt đã thực thi | `notebooks/benchmark_analysis.executed.ipynb` |
| Dashboard 8 trang và 6 loại bộ lọc | `dashboard/app.py` |
| Quyết định theo workload/SLA/bằng chứng; 8 case minh họa | `benchmark/decision_engine/`, `reports/generated/demo/decision/` |
| Báo cáo và bảng CSV sẵn dùng | `reports/generated/demo/` |
| Kết quả kiểm tra local bằng k6 thật | `results/local_smoke/summary.json` |

## Cấu hình API thật

Trong `.env` nhập:

```dotenv
IAAS_URL=https://YOUR_IAAS_API
PAAS_URL=https://YOUR_CLOUD_RUN_API
FAAS_URL=https://YOUR_GEN2_FUNCTION_API
GCP_PROJECT_ID=your-project-id
```

Đây chỉ là mẫu: phải thay URL. URL không nằm trong source JS. Với API private, đặt `IAAS_TOKEN`, `PAAS_TOKEN`, `FAAS_TOKEN` là **ID token có audience đúng**. `gcloud auth print-identity-token --audiences=...` phù hợp khi dùng danh tính/service account được hỗ trợ; người vận hành phải xác minh audience và quyền invoker. ADC cho collector không tự cấp quyền gọi API private. Token có hạn; làm mới trước run dài, không ghi token vào YAML, metadata hoặc Git.

Chỉnh `configs/targets.yaml` theo OpenAPI **thật của nhóm**: path/method/status, request template, response schema, trường ignore khi so payload, optional `success_field`/`success_value` cho business errors. Thay `read_ids` bằng tập ID tồn tại đã kiểm tra; không dùng ID ghi benchmark làm read seed. Ghi `dataset_id`/Firestore location. Với write adapter, giữ namespace `bench-` và `benchmark_run_id`; dùng cùng payload ở ba deployment.

Điền `service` thật của Cloud Run và **backing service** của functions gen2; `function_name`, `instance_name`, `instance_id`, `zone`. Concurrency khai báo `null` có nghĩa chưa xác minh; collector đọc cấu hình thật qua API, không giả định concurrency bằng 1 hoặc 80.

## Credentials và IAM

Cài [gcloud CLI](https://cloud.google.com/sdk/docs/install), rồi trên máy có quyền:

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
```

Trên VM tạo tải ưu tiên service account gắn với VM, quyền tối thiểu và scope phù hợp. Không commit service account key. Các API cần được chủ dự án bật trước; toolkit không tự bật API hay tạo tài nguyên.

Quyền đọc cần thiết tùy module: `roles/monitoring.viewer`, `roles/run.viewer`, `roles/cloudfunctions.viewer`, `roles/compute.viewer`; thêm `roles/logging.viewer` nếu đọc application logs. Private gen2 HTTP cần `roles/run.invoker` trên backing service. ADC quota project có thể cần `roles/serviceusage.serviceUsageConsumer`. SSH đọc Docker evidence cần quyền SSH/OS Login do chủ hạ tầng cấp riêng; không cần quyền xóa/triển khai tài nguyên.

## Quy trình benchmark thật

1. Đọc [benchmark protocol](docs/benchmark_protocol.md) và [integration guide](docs/integration_guide.md).
2. Chạy pilot nhỏ để xác định max VU, khả năng máy k6, quota Firestore và trần RPS.
3. Trong `experiments.yaml`, nhập **trần chi phí bảo thủ đã kiểm chứng** `/request` và `/hour`, budget, max_requests, max_rps; bật `quota_verified`, `allow_benchmark_writes` sau khi kiểm tra.
4. Default `comparison_mode: controlled` yêu cầu evidence Docker limits và concurrency/CPU/memory PaaS/FaaS được đọc thực tế. Hoặc chọn `deployment` để nghiên cứu cấu hình triển khai thực tế và báo confounders rõ ràng.
5. Chạy dry-run, xem toàn bộ kế hoạch; rồi validate live và chạy benchmark.

```bash
python -m benchmark.cli run-all --dry-run --repeats 5
python -m benchmark.cli validate --live
python -m benchmark.cli run --scenario steady --target iaas --level low --repeats 5
python -m benchmark.cli run --scenario burst --target paas --repeats 5
python -m benchmark.cli run --scenario idle --target faas --repeats 5
python -m benchmark.cli run --scenario steady --target paas --endpoint cpu --repeats 5
python -m benchmark.cli run-all --repeats 5
python -m benchmark.cli run-all --repeats 5 --resume
```

`run-all` mặc định 75 run: 3 mô hình × (3 steady levels + burst + idle) × 5 vòng. Thứ tự model được shuffle có seed trong mỗi block, không chạy đồng thời trên Firestore chung. Một `run` cũng mặc định 5 lần; giữ cùng thời lượng/mix/CPU input giữa các model. Đo endpoint đơn bằng `--endpoint read|write|cpu`.

Idle thực sự do Python chờ 1.200 giây, không giữ k6 chạy. Runner lấy samples Monitoring khi idle, sau đó mới phát request đầu và warm requests. Không tự khởi động lại VM/container. Samples zero chỉ là bằng chứng đã quan sát zero tại thời điểm sample, không tự xác nhận request hiện tại cold.

Default kế hoạch có thể vượt `max_requests: 100000`; runner sẽ từ chối, không tự tăng giới hạn. Giảm số kịch bản/tải hoặc cập nhật giới hạn sau pilot có căn cứ. Ngân sách ledger giữ nguyên phần đã reserve cho attempt thất bại/gián đoạn. Đây là chính sách bảo thủ theo bound đầu vào, **không phải hard cap hóa đơn GCP** và không kiểm soát VM/dịch vụ khác vẫn chạy ngoài thí nghiệm. Xem [cost assumptions](docs/cost_assumptions.md).

Runner lưu `results/raw/<run-id>/attempt-NNN/`: k6 raw/summary, stdout/stderr, compatibility, fairness, Monitoring, logs nếu bật, generator samples, metadata, source hashes. Lỗi vẫn giữ dữ liệu một phần. `resume` chỉ bỏ qua attempt `COMPLETE` có cùng fingerprint; raw attempt cũ được giữ. Không có cleanup cloud tự động.

## Thu thập và phân tích dữ liệu thật

```bash
python -m benchmark.cli collect --target paas --start 2026-10-31T01:00:00Z --end 2026-10-31T01:10:00Z --output results/monitoring/paas.json
python -m benchmark.cli analyze --input results --output results/processed/real
```

Để collector tự tích hợp, để `monitoring.enabled: true`; mặc định chờ 180 giây sau k6 cho metric xuất hiện. Muốn thu hồi dữ liệu trễ hơn, chạy collect rồi đặt bản kết quả đúng run directory. Các GCE metric không giống Cloud Run; RAM VM cần Ops Agent, xem integration guide.

Không đặt dữ liệu local smoke hay demo trong `results/raw/` của REAL. Parser hỗ trợ native JSONL và CSV từ k6. Native JSONL chứa `request_sample_ms` do script đi kèm tạo giúp join chính xác từng request. Với file ngoài chỉ có `http_req_duration`, parser có fallback nhưng không suy diễn business result, handler time hoặc cold evidence; quality cảnh báo và không dùng CI chính thức.

## Chi phí, hòa vốn và độ nhạy

```bash
python -m benchmark.cli cost
python -m benchmark.cli cost --workload configs/cost_workloads.yaml --max-requests 1000000000
python scripts/snapshot_prices.py
python scripts/export_billing_catalog.py --list-services
```

Giá có nguồn trong `configs/pricing_catalog.yaml`. Giá VM, Cloud Run request/instance, Firestore và disk Singapore đã đối chiếu bảng public; `effective_date`/numeric SKU ID để `null` khi nguồn public không cung cấp. Các SKU phụ thuộc route/machine chưa chọn có `null`; **nếu quantity > 0 thì model báo lỗi yêu cầu cập nhật**, không điền giá tưởng tượng. Script snapshot chỉ cập nhật bằng chứng, không tự thay catalog đã review.

`configs/cost_workloads.yaml` có 100.000 / 2.000.000 / 20.000.000 request/tháng, mix 70/20/10 và uniform/business/bursty profile. Mean service/CPU demand hiện là **giả định DEMO**, không lấy từ số đo GCP. Để dùng REAL, sao chép file, đặt `data_mode: REAL`, nhập mean/cpu/profile/usage thực tế cùng nguồn ghi nhận; dùng `--workload đường-dẫn-file` và `--output results/financial/real`.

Free tier mặc định **tắt**. Chỉ bật khi xác minh billing-account remaining allowance và điều kiện Firestore default database; không nhân free tier cho cả ba dịch vụ cùng chạy chung tài khoản. Mô hình so sánh các phương án thay thế loại trừ nhau; xem hướng dẫn chi tiết.

IaaS capacity chưa đo là `UNVERIFIED`. Vượt capacity là `UNSUPPORTED_CAPACITY`; giá một VM lúc đó không chứng minh workload được phục vụ. PaaS/FaaS cấu hình giống nhau có thể có chi phí giống hệt; hòa vốn trả `COINCIDENT_INTERVAL`. Không có nghiệm hoặc bước nhảy được báo riêng.

## Xuất hình, báo cáo và decision engine

```bash
python -m benchmark.cli export
python -m benchmark.cli export --analysis results/processed/real --financial results/financial/real --output charts/real --reports reports/generated/real
python -m benchmark.cli decision
```

Hình nằm trong `charts/<mode>/`; footer ghi mode và file nguồn, `chart_manifest.json` liệt kê provenance. Output báo cáo gồm CSV UTF-8 BOM, **Excel `.xlsx`**, JSON, Markdown và HTML. Workbook dùng openpyxl theo lựa chọn của người dùng: Overview, công thức tổng hợp cohort, đối soát chi phí, biểu đồ native, CI/scaling/errors, giả định và source URLs. Các kết quả SciPy/occupancy/sensitivity là snapshot từ Python; sửa YAML rồi chạy lại pipeline để cập nhật. Excel tự tính công thức tổng hợp khi mở. Tách mode ở thư mục và trong từng bảng; exporter từ chối trộn mode.

`benchmark.decision_engine.recommend(Workload(...), evidence, policy)` kiểm tra control, nhân lực vận hành, security allowlist, portability, background/timeout, p95 CI, error, peak capacity, cold tolerance và budget. Cần xác nhận scope đại diện workload. Thiếu bằng chứng trả `INCONCLUSIVE`; mặc định dữ liệu DEMO không tạo đề xuất thực nghiệm. `decision` không có input sinh 8 case **minh họa mô phỏng**; để đánh giá thực, truyền cả `--workload <json> --evidence <json>`.

## Notebook và dashboard

```bash
python scripts/execute_notebook.py
python -m streamlit run dashboard/app.py
```

Notebook gốc có parameter qua env `BENCH_MODE`, `BENCH_DATA_ROOT`, `BENCH_COST_WORKLOAD`. Bản `.executed.ipynb` lưu outputs và execution counts. Muốn mở UI tương tác: `python -m pip install jupyterlab` rồi `python -m jupyterlab notebooks/benchmark_analysis.ipynb` (gói UI tùy chọn). Dashboard chỉ đọc output đã tạo; chọn REAL khi chưa có dữ liệu sẽ hiển thị thiếu, không tự chuyển sang demo.

## Kiểm thử

```bash
python -m pytest -q
python -m ruff check benchmark scripts dashboard examples tests
python scripts/local_smoke.py
```

Local smoke khởi chạy ba API fixture trong `examples/mock_api.py`, kiểm tra contract, chạy cả 6 script k6 với 12 jobs, parse raw thật và dừng các process fixture khi xong. Đây là test tích hợp, không là cloud benchmark; raw có `data_mode: LOCAL_TEST`. Bộ test kiểm tra percentile/CI, zero-request, missing metrics, outliers, duplicate, cold evidence, scale interval, cost/free tier/capacity, nhiều kiểu giao điểm, decision rules và UI.

## Lỗi thường gặp

| Lỗi | Xử lý |
|---|---|
| URL chưa cấu hình / contract fail | Nhập `.env`, chỉnh endpoint mapping/schema theo OpenAPI thật; xem compatibility.json |
| Thiếu ADC / permission denied | Cấu hình ADC, quota project, API enabled và roles đúng resource |
| Controlled resource verification fail | Thu Docker evidence, điền đúng instance/service; xác minh cùng limits/concurrency hoặc dùng deployment mode và báo confounders |
| Budget / quota chưa verified | Kiểm chứng trần giá và quota trước; toolkit không tự tăng budget |
| Dropped iterations / saturation | Tăng capacity máy tạo tải/VU sau pilot, giảm rate; giữ run invalid trong hồ sơ |
| Monitoring NO_DATA | Chờ thêm sampling/visibility delay, kiểm tra resource labels, service backing gen2 và Ops Agent |
| `PriceMissingError` | Chọn đúng SKU/region/route, nhập giá và nguồn vào catalog; quantity 0 mới không cần giá |
| `runner.lock` còn sau kill | Kiểm tra PID/process; chỉ xóa lock sau khi chắc chắn không có runner đang hoạt động |
| Chart thiếu dữ liệu / CI trống | Xem quality, số run hợp lệ và kích thước mẫu; không điền số giả |

Chi tiết bàn giao và các bước chưa đo thật: [reports/handover_checklist.md](reports/handover_checklist.md).
