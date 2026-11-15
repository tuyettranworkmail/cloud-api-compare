# Nhật ký vận hành — Phúc Hoàng

**Đề tài:** So sánh thực nghiệm IaaS, PaaS và FaaS cho cùng một API  
**Người thực hiện:** Phúc Hoàng  
**Phạm vi:** Thiết lập benchmark, xác minh hạ tầng và API contract  
**Google Cloud Project:** `ccapi-tran-2026`  
**Vùng triển khai:** `asia-southeast1`

## 2026-11-11 — T2: Thiết lập và kiểm tra IaaS

- Kết nối từ Loadgen VM đến IaaS API qua địa chỉ nội bộ `http://10.10.0.4`.
- Kiểm tra `GET /health`: HTTP 200.
- Kiểm tra `GET /openapi.json`: HTTP 200.
- Kiểm tra `GET /items/item-000001`: HTTP 200, đọc được dữ liệu mẫu.
- Kiểm tra `GET /compute?n=1000`: HTTP 200.
- Lưu bằng chứng kiểm tra tại `results/t2-evidence/`:
  - `health.json`
  - `openapi.json`
  - `read.json`
  - `compute.json`
  - `summary.txt`
- Xác minh 5 file bằng chứng đã được tải về máy local.

**Kết quả:** Các endpoint smoke test được kiểm tra đều trả HTTP 200.

**Lỗi gặp phải và cách xử lý:**
- SCP ban đầu không tìm thấy thư mục bằng chứng.
- Có lần chạy nhầm lệnh SCP trong phiên SSH Linux thay vì PowerShell.
- Khắc phục bằng cách thoát SSH và chạy SCP từ Windows PowerShell với đường dẫn đầy đủ.

**Giới hạn:**
- Đây là smoke test, chưa phải benchmark tải chính thức.
- `live_contracts/cloud_benchmark` ở bước validate cấu hình local có trạng thái `NOT_EXECUTED`.
- Chưa thực hiện write test và chưa kết luận tương đương dữ liệu.

**Bằng chứng:** `results/t2-evidence/`.

## 2026-11-12 — T3: Xác minh cấu hình IaaS

- Kiểm tra thông tin VM trên Google Compute Engine.
- Instance ID: `4901182592617265517`.
- Machine type: `e2-standard-2`.
- Zone: `asia-southeast1-b`.
- Cấu hình VM: 2 vCPU, 8192 MiB RAM.
- Trạng thái tại thời điểm kiểm tra: `RUNNING`.
- Cập nhật instance ID trong `configs/targets.yaml`.

**Giới hạn:**
- Chưa xác minh giới hạn CPU và RAM thực tế của Docker container bằng `docker inspect`.
- Chưa đủ bằng chứng xác nhận tài nguyên container thực tế khớp cấu hình khai báo.

## 2026-11-12 — T3: Contract Test PaaS

- Kiểm tra endpoint và OpenAPI của PaaS.
- Cập nhật thông tin dịch vụ PaaS trong `configs/targets.yaml`.
- GET read: 3 trials — PASS.
- GET CPU: 2 trials — PASS.
- Không thực hiện thao tác ghi dữ liệu (`writes_executed=false`).
- Lưu kết quả tại `results/t3/paas-contract-verified-20261112.json`.

## 2026-11-12 — T3: Contract Test FaaS

- Xác minh OpenAPI trả HTTP 200.
- Xác nhận các endpoint `/compute`, `/health`, `/items`, `/items/{item_id}`.
- Revision `ccapi-faas-00003-fin` ở trạng thái ACTIVE, nhận 100% traffic tại thời điểm kiểm tra.
- Cấu hình xác minh: 1 CPU, 1 GiB RAM, timeout 60 giây, maximum instances 10, concurrency 1.
- Kiểm tra IAM invoker và service account.
- GET read: 3 trials — PASS.
- GET CPU: 2 trials — PASS.
- Không thực hiện thao tác ghi dữ liệu (`writes_executed=false`).
- Lưu kết quả tại `results/t3/faas-contract-verified-20261112.json`.

## 2026-11-12 — T3: Đối chiếu contract ba mô hình

- Thực hiện live contract validation cho IaaS, PaaS và FaaS.
- Cả ba mô hình đều PASS:
  - GET read: 3 trials.
  - GET CPU: 2 trials.
- Contract hash chung: `7e491088e96952e85ac228f2e1e5e4faaf8e39fae49f82cf62b2fa37eb291f17`.
- Không thực hiện write test.
- `equivalence_checked=false`.

**Lưu ý:** Contract hash giống nhau không chứng minh payload hoặc dữ liệu trả về tương đương hoàn toàn. Không dùng kết quả này để kết luận tương đương dữ liệu hoặc hiệu năng.

## 2026-11-12 — T3: Kiểm tra Billing và tổng hợp báo cáo

- Truy vấn Google Cloud Billing Budgets API.
- Lưu kết quả tại `results/t3/billing-budgets.json`.
- Kết quả trả về `[]`, nhưng tài khoản hiện tại không có đủ quyền truy cập billing account.
- Phân loại: **BLOCKED — INSUFFICIENT PERMISSIONS**. Không kết luận billing account không có budget.
- Tạo báo cáo `reports/t3-infrastructure-validation-2026-11-12.md`.
- Báo cáo phân loại rõ PASS, BLOCKED và NOT VERIFIED.

## Số bước thao tác và thời gian thực tế

- Số bước thao tác: Chưa chuẩn hóa và thống kê.
- Thời gian thực tế: Chưa đo tổng thời gian từ đầu đến cuối.
- Không tự ước lượng thời gian khi chưa có dữ liệu đo.

## Việc người vận hành phải tự quản

- **IaaS:** Quản lý VM, OS, Docker runtime, tài nguyên container, cập nhật, giám sát và backup.
- **PaaS:** Quản lý ứng dụng, cấu hình dịch vụ, phiên bản triển khai, IAM và giám sát.
- **FaaS:** Quản lý mã nguồn function, runtime, IAM, giới hạn tài nguyên và giám sát invocation.
- **Billing:** Cần quyền phù hợp để kiểm tra budget và đối chiếu chi phí.

## Việc chưa hoàn thành / chưa đủ bằng chứng

- Chưa xác minh Docker container limits trên IaaS.
- Chưa xác minh payload/data equivalence giữa ba mô hình.
- Chưa thực hiện benchmark hiệu năng chính thức.
- Chưa có bằng chứng nền tảng đủ để xác nhận cold start.
- Chưa đo đầy đủ autoscaling và scale-out.
- Chưa đối chiếu hóa đơn thực tế do thiếu quyền Billing.
- Chưa đo quy trình sửa lỗi đến phát hành.

## Commit ghi nhận T3

- Commit: `6cb6a23`
- Nội dung: `test(t3): verify IaaS PaaS FaaS contracts and evidence`
- Trạng thái: Đã commit trên nhánh `feat/phuc-hoang/benchmark`, chưa push tại thời điểm ghi nhật ký.



## 2026-11-15 — T4: Chuẩn bị và kiểm chứng benchmark

### 1. Điều chỉnh workload
- Cập nhật `configs/workloads.yaml` để giảm tải và hạn chế chi phí thử nghiệm.
- Steady workload: 1, 2, 3 RPS.
- Burst workload: baseline 1 RPS, peak 3 RPS.
- Idle workload: 60 giây.
- Preallocated VUs: 5; maximum VUs: 10.
- Cập nhật `configs/experiments.yaml` với giới hạn ngân sách 10 USD, tối đa 5.000 requests và 10 RPS.

### 2. Dry-run
- Chạy lệnh:
  `python -m benchmark.cli run-all --endpoint read --repeats 1 --dry-run`
- Kế hoạch gồm 15 runs cho 3 mô hình và 3 kịch bản.
- Request bound: 744.
- Maximum planned RPS: 3.
- Dry-run hoàn thành, không gửi request đến cloud.
- Đây là kiểm tra cấu hình, không phải kết quả benchmark thực tế.

### 3. Kiểm tra quota và Monitoring
- Kiểm tra Compute Engine quota toàn vùng:
  - Limit: 16 CPUs.
  - Usage: 4 CPUs.
  - Remaining: 12 CPUs.
- Kiểm tra Cloud Run service quotas.
- Xác nhận Monitoring API đã được bật.
- Lưu ý: quota đọc/ghi API quản lý Cloud Run không đại diện cho HTTP runtime RPS.
- Chưa đủ bằng chứng để đặt `quota_verified=true`.

### 4. Kiểm tra Billing và giá dịch vụ
- Xác định Service ID của Compute Engine, Cloud Run, Cloud Run Functions và Cloud Firestore.
- Gọi thành công Billing Account Price API.
- Tra cứu SKU IPv4 `C054-7F72-A02E`.
- API trả về thông tin giá theo VND và mức giảm giá tài khoản bằng 0 cho SKU đã kiểm tra.
- Tiếp tục truy xuất SKU Compute Engine theo phân trang để tìm đúng SKU vùng `asia-southeast1`.
- Chưa hoàn tất đối chiếu giá tài khoản cho toàn bộ dịch vụ.
- Các giá trong pricing catalog chưa được xem là trần chi phí đã xác minh.

### 5. Kiểm tra điều kiện chạy REAL
- Kiểm tra safety guard trong `benchmark/runner.py`.
- Runner yêu cầu `verified_upper_usd_per_request` và `verified_upper_usd_per_hour` phải có giá trị hợp lệ.
- Hiện hai giới hạn này chưa được xác minh.
- `quota_verified` vẫn là `false`.
- Dry-run ghi nhận thiếu trần chi phí đã kiểm chứng nên không cho phép chạy REAL.
- Không vô hiệu hóa safety guard hoặc tự đặt giá trị chi phí giả định.

### 6. Hạ tầng IaaS
- Xác nhận VM `ccapi-iaas-api` đang RUNNING.
- Machine type: `e2-standard-2`.
- Zone: `asia-southeast1-b`.
- Cấu hình: 2 vCPU, 8 GB RAM.

### Kết luận T4 tại ngày 15/11
- Workload và dry-run: PASS.
- Kiểm tra Billing API: PASS đối với SKU IPv4 đã tra cứu.
- Xác minh đầy đủ chi phí: NOT VERIFIED.
- Xác minh quota để chạy REAL: NOT VERIFIED.
- REAL benchmark: NOT EXECUTED.
- Chưa có kết quả thực nghiệm để so sánh hiệu năng và chi phí IaaS/PaaS/FaaS.

## 2026-11-15 — T4: Rà soát backup và dọn dẹp

- Kiểm kê các file backup và snapshot trong repository.
- So sánh hash giữa 7 bản backup mã nguồn/cấu hình với file hiện tại.
- Kết quả: cả 7 bản đều khác file hiện tại, không xóa để bảo toàn khả năng rollback.
- Xóa `.env.before-url-fix.bak` vì đây là bản môi trường cũ, có thể chứa thông tin nhạy cảm.
- Giữ nguyên `.env` hiện tại.
- Không xóa dữ liệu trong `results/`, `reports/`, `configs/` hoặc các bằng chứng T4.
- Chưa thực hiện REAL benchmark; các điều kiện xác minh chi phí và quota vẫn đang được xử lý.

