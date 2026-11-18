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



---

# Nhật ký công việc bổ sung – 2026-11-18

**Đề tài:** So sánh thực nghiệm IaaS, PaaS và FaaS cho cùng một API
**Người thực hiện:** Phúc Hoàng
**Repository:** `cloud-api-compare`
**Google Cloud Project:** `ccapi-tran-2026`
**Phạm vi:** Rà soát benchmark, hỗ trợ cấu hình và kiểm tra API, theo dõi pilot, phân tích kết quả và ghi nhận hạn chế.

## 1. Nhiệm vụ 1 – Rà soát protocol, cấu hình và mã nguồn benchmark

**Mục tiêu:** Kiểm tra tính nhất quán giữa protocol benchmark, cấu hình target và cách chương trình gửi request trước khi thực hiện benchmark.

**Công việc đã thực hiện:**

- Kiểm tra cấu trúc repository và các thư mục cấu hình:
  - `configs/`: cấu hình benchmark chính thức.
  - `configs-pilot/`: cấu hình dành cho pilot.
  - `benchmark/runner.py`: chương trình điều phối benchmark.
- Rà soát các file:
  - `benchmark/config.py`
  - `benchmark/runner.py`
  - `benchmark/validators.py`
  - `configs/targets.yaml`
  - `benchmark/collectors/gcp.py`
- Kiểm tra thông số protocol: `repeats=1`, các mức tải 1/2/3 RPS, warmup 5 giây, measurement 10 giây; cấu hình burst có peak 3 RPS và hold 3 giây.
- Kiểm tra điều kiện an toàn trước benchmark:
  - Cost bounds chưa được thiết lập (`null`).
  - `quota_verified=false`.
  - `allow_benchmark_writes=false`.
- Kiểm tra luồng xác thực request:
  - `request_headers()` trong `benchmark/config.py` đọc các biến `IAAS_TOKEN`, `PAAS_TOKEN`, `FAAS_TOKEN`.
  - Validator sử dụng request GET read-only và kiểm tra OpenAPI.
  - Runner kiểm tra metadata zone và instance ID.
  - Tại thời điểm rà soát ban đầu, luồng chưa tự lấy identity token cho PaaS/FaaS.
  - Runner chuyển headers cho k6 thông qua file tạm `private_runtime_config.json` và có bước dọn file sau khi chạy.

**Kết quả:**

- Xác định được luồng request và vị trí xử lý authentication.
- Phát hiện điểm cần hoàn thiện đối với việc lấy identity token cho PaaS/FaaS.
- Xác định các điều kiện an toàn chưa đạt để chạy REAL benchmark.

**Giới hạn và trạng thái:**

- Đây là hoạt động rà soát và xác minh mã nguồn/cấu hình.
- Đã bổ sung patch lấy GCE Metadata identity token cho PaaS/FaaS khi không có token từ biến môi trường; chưa xác minh end-to-end trên môi trường cloud.
- Chưa thực hiện POST/write test.
- Chưa thực hiện REAL benchmark.
- Chưa đủ điều kiện xác nhận benchmark chính thức an toàn và hợp lệ.

## 2. Nhiệm vụ 2 – Hỗ trợ cấu hình và kiểm tra API cho benchmark

**Mục tiêu:** Hỗ trợ quá trình chuẩn bị môi trường, kiểm tra khả năng truy cập API và xác minh các endpoint trước khi chạy tải.

**Công việc đã thực hiện:**

- Kiểm tra thông tin các target IaaS, PaaS và FaaS trong cấu hình.
- Hỗ trợ rà soát cấu hình và luồng chạy benchmark.
- Kiểm tra kết nối đến PaaS và FaaS từ môi trường `benchmark-loadgen`.
- Thực hiện functional smoke test với các endpoint:
  - `GET /items/item-000001`
  - `GET /items/item-000002`
  - `GET /items/item-000003`
  - `GET /compute?n=1000`
- Kết quả kiểm tra PaaS: 4/4 request trả HTTP 200.
- Kết quả kiểm tra FaaS: 4/4 request trả HTTP 200.
- Kiểm tra lại môi trường thực thi lệnh và sử dụng `/usr/bin/curl` sau khi khôi phục PATH.

**Kết quả:**

- Xác nhận các endpoint đọc dữ liệu và tính toán của PaaS/FaaS có thể phản hồi thành công trong lần smoke test.
- Hỗ trợ chuẩn bị và kiểm tra cấu hình phục vụ các bước benchmark tiếp theo.

**Giới hạn và trạng thái:**

- Smoke test không thay thế benchmark tải.
- Chưa xác nhận đầy đủ luồng authentication tự động cho PaaS/FaaS.
- Chưa thực hiện POST/write test.
- Chưa có kết quả REAL benchmark từ Loadgen VM để kết luận hiệu năng ba mô hình.

## 3. Nhiệm vụ 3 – Theo dõi và xác minh kết quả các pilot C01–C04

**Mục tiêu:** Theo dõi từng lượt pilot, kiểm tra artifact sau khi chạy và xác minh kết quả trước khi đưa vào phân tích.

**Công việc đã thực hiện:**

- Kiểm tra các thư mục kết quả:
  - `results/pilot/c01-paas-steady-low/`
  - `results/pilot/c02-faas-steady-low/`
  - `results/pilot/c03-paas-steady-low-cpu/`
  - `results/pilot/c04-paas-burst-low-read/`
- Kiểm tra các artifact chính:
  - `k6.jsonl`
  - `summary.json`
  - `monitoring.json`
- Kiểm tra thêm metadata, execution log, generator và fairness evidence đối với các pilot có cung cấp.
- Đối chiếu số request, HTTP status, thời gian đo và thông tin monitoring.
- Kiểm tra riêng pilot C04: execution hoàn thành, exit code 0, không có dropped iterations, tổng số request được gửi là 102 trong measurement 44 giây.

**Kết quả xác minh các pilot:**

| Pilot | Mô hình / kịch bản     | Request | HTTP thành công | Avg latency (measurement) |
| ----- | ---------------------- | ------: | --------------: | ------------------------: |
| C01   | PaaS – steady low-read |      31 |           31/31 |                  73.29 ms |
| C02   | FaaS – steady low-read |      30 |           30/30 |                  60.83 ms |
| C03   | PaaS – steady low-CPU  |      31 |           31/31 |                  47.24 ms |
| C04   | PaaS – burst low-read  |      92 |           92/92 |                  59.79 ms |

_Các số request trong bảng là measurement, không bao gồm warmup. C01–C04 đều có thêm 10 request warmup._

**Riêng C04:**

- Execution status: `COMPLETE`.
- Exit code: `0`.
- Offered requests: 102.
- Dropped iterations: 0.
- Measurement duration: 44 giây.
- Cloud Monitoring ghi nhận 68 HTTP-200 observations trong bucket lấy mẫu.
- Monitoring có độ trễ và chu kỳ lấy mẫu riêng; không lấy 68 observations chia cho 102 request k6 để suy ra số request thất bại.

**Giới hạn:**

- C01–C04 là laptop pilot, có `comparable=false`.
- Chưa phải kết quả benchmark chính thức trên cùng Loadgen VM và cùng điều kiện hạ tầng.
- C04 chưa chứng minh được scale-out; fairness được phân loại `NOT_ASSESSED_SINGLE_TARGET`.

## 4. Nhiệm vụ 4 – Phân tích latency, throughput và error rate

**Mục tiêu:** Tổng hợp số liệu từ artifact pilot, phân tích khả năng phản hồi và chuẩn bị dữ liệu so sánh giữa các mô hình.

**Công việc đã thực hiện:**

- Đọc và đối chiếu `k6.jsonl`, `summary.json` và `monitoring.json`.
- Phân biệt số liệu warmup với measurement.
- Tổng hợp latency Min, Avg, P50, P95, P99 và Max.
- Kiểm tra HTTP success, request count và dropped iterations.
- Đối chiếu kết quả k6 với Cloud Monitoring, tránh trộn lẫn hai nguồn có chu kỳ lấy mẫu khác nhau.

**Latency measurement của các pilot:**

| Pilot | Min (ms) | Avg (ms) | P50 (ms) | P95 (ms) | P99 (ms) | Max (ms) |
| ----- | -------: | -------: | -------: | -------: | -------: | -------: |
| C01   |    55.70 |    73.29 |    61.54 |    91.23 |   317.31 |   317.31 |
| C02   |    51.48 |    60.83 |    56.69 |    74.41 |    88.72 |    88.72 |
| C03   |    43.94 |    47.24 |    46.51 |    55.62 |    61.27 |    61.27 |
| C04   |    51.43 |    59.79 |    56.10 |    77.25 |    87.13 |    87.13 |

**Nhận xét sơ bộ:**

- Các pilot có artifact measurement đều ghi nhận request thành công HTTP 200.
- C03 có average latency thấp nhất trong bốn pilot được kiểm tra.
- C01 có P99 và Max cao hơn đáng kể so với P50, cho thấy có request latency tăng đột biến.
- C02 và C04 có P95/P99 thấp hơn C01 trong các lượt đo tương ứng.
- Không thể dùng các số liệu này để kết luận FaaS tốt hơn PaaS hoặc xếp hạng ba mô hình, vì kịch bản, môi trường và điều kiện đo chưa được chuẩn hóa để so sánh công bằng.
- Chưa có bộ số liệu IaaS tương ứng trong cùng điều kiện pilot để hoàn thành bảng so sánh ba mô hình.

**Trạng thái:**

- Đã thực hiện phân tích sơ bộ latency và HTTP success của C01–C04.
- Chưa đủ dữ liệu để kết luận throughput và error rate chính thức giữa IaaS, PaaS và FaaS.
- Chưa hoàn thành báo cáo so sánh hiệu năng chính thức của cả ba mô hình.

## 5. Nhiệm vụ 5 – Ghi nhận hạn chế, rủi ro và bằng chứng còn thiếu

**Mục tiêu:** Xác định các điều kiện chưa đạt, tránh sử dụng pilot hoặc bằng chứng chưa đầy đủ để đưa ra kết luận chính thức.

**Các vấn đề đã ghi nhận:**

1. **IaaS resource verification**
   - Chưa có bằng chứng đầy đủ về CPU/RAM limit thực tế của Docker container.
   - Chưa xác minh đầy đủ tài nguyên IaaS để đối chiếu với PaaS/FaaS.

2. **Authentication**
   - Đã bổ sung cơ chế tự lấy identity token qua GCE Metadata Server; việc xác minh end-to-end trên môi trường cloud vẫn chưa hoàn tất.
   - Cần bảo đảm token được xử lý an toàn, không ghi token nhạy cảm vào log.

3. **Cost và quota**
   - Cost bounds còn `null`.
   - `quota_verified=false`.
   - Chưa đủ bằng chứng về giới hạn chi phí an toàn cho REAL benchmark.

4. **Data equivalence**
   - Chưa hoàn thành kiểm tra payload/data equivalence giữa ba mô hình.
   - Contract hash giống nhau không thay thế được kiểm tra nội dung dữ liệu thực tế.

5. **Benchmark fairness**
   - C01–C04 là laptop pilot và được đánh dấu `comparable=false`.
   - C04 có `controlled_limits_verified=false`.
   - Chưa có bộ benchmark chính thức cùng điều kiện cho cả ba mô hình.

6. **Autoscaling và cold start**
   - Chưa có bằng chứng đầy đủ về cold start.
   - Chưa xác minh được scale-out trong điều kiện tải phù hợp.
   - Không suy luận autoscaling chỉ từ một lượt pilot hoặc một snapshot tài nguyên.

7. **Billing**
   - Chưa đủ quyền để đối chiếu đầy đủ Billing Budgets và chi phí thực tế.

8. **Official benchmark**
   - Chưa có kết quả REAL benchmark đầy đủ từ GCP Loadgen.
   - Chưa đủ căn cứ để công bố kết luận hiệu năng hoặc chi phí giữa ba mô hình.

**Trạng thái hạ tầng tại ngày 18/11/2026:**

- `benchmark-loadgen`: `TERMINATED`.
- `ccapi-iaas-api`: `TERMINATED`.
- Cloud Run PaaS/FaaS có min instances bằng 0.
- Cần lưu ý reserved static external IPv4 có thể tiếp tục phát sinh chi phí ngay cả khi VM đã dừng.

**Kết luận nhiệm vụ:**

Đã tổng hợp và ghi nhận các hạn chế, rủi ro và bằng chứng còn thiếu. Chưa xác nhận đủ điều kiện để chạy hoặc công bố kết quả REAL benchmark chính thức.

## Tổng kết 5 nhiệm vụ bổ sung

| Nhiệm vụ | Nội dung                                    | Trạng thái                                                                  |
| -------- | ------------------------------------------- | --------------------------------------------------------------------------- |
| 1        | Rà soát protocol, config và benchmark code  | Đã rà soát, còn điểm cần hoàn thiện                                         |
| 2        | Hỗ trợ cấu hình và kiểm tra API             | Đã hỗ trợ smoke test, chưa hoàn tất REAL benchmark                          |
| 3        | Theo dõi và xác minh pilot C01–C04          | Đã kiểm tra artifact và kết quả pilot                                       |
| 4        | Phân tích latency, throughput và error rate | Đã phân tích latency/HTTP success sơ bộ; chưa đủ dữ liệu so sánh chính thức |
| 5        | Ghi nhận hạn chế và bằng chứng thiếu        | Đã tổng hợp và phân loại                                                    |

**Phạm vi đóng góp cá nhân:** Tập trung vào rà soát cấu hình và luồng kiểm thử, hỗ trợ xác minh API, theo dõi kết quả sau mỗi lượt đo, phân tích số liệu hiệu năng và ghi nhận những phần chưa đủ căn cứ. Các kết quả pilot được giữ đúng phạm vi thử nghiệm, không sử dụng thay cho benchmark chính thức.
