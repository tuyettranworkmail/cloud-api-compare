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


