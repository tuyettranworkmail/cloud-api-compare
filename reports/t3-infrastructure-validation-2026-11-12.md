# T3 – Cloud Infrastructure and Contract Validation

**Ngày xác minh:** 2026-11-12  
**Phạm vi:** IaaS, PaaS, FaaS trên Google Cloud  
**Kết luận:** PASS cho contract validation; chưa đủ bằng chứng để kết luận tương đương dữ liệu, hiệu năng, chi phí hoặc khả năng mở rộng.

## 1. Executive summary

Đã thực hiện live contract validation cho ba mô hình triển khai:

| Model | Read endpoint | CPU endpoint | Contract |
|---|---:|---:|---|
| IaaS | GET – 3 trials PASS | GET – 2 trials PASS | PASS |
| PaaS | GET – 3 trials PASS | GET – 2 trials PASS | PASS |
| FaaS | GET – 3 trials PASS | GET – 2 trials PASS | PASS |

Tất cả các contract validation đều không ghi dữ liệu (`writes_executed=false`), không có lỗi được ghi nhận trong kết quả xác minh (`errors=[]`).

Cả ba kết quả có cùng contract hash:

`7e491088e96952e85ac228f2e1e5e4faaf8e39fae49f82cf62b2fa37eb291f17`

Điều này xác nhận contract được kiểm tra có cùng fingerprint. Nó không tự chứng minh dữ liệu trả về giữa ba nền tảng tương đương (`equivalence_checked=false`).

## 2. Evidence theo nền tảng

### 2.1 IaaS

Contract validation:
- GET read: 3 trials, PASS.
- GET CPU: 2 trials, PASS.
- Writes executed: false.
- Equivalence checked: false.

VM snapshot:
- Instance ID: `4901182592617265517`.
- Machine type: `e2-standard-2`.
- Zone: `asia-southeast1-b`.
- VM: 2 vCPU, 8192 MiB RAM.
- Status tại thời điểm snapshot: `RUNNING`.
- Declared application limits: 1 vCPU, 1 GiB RAM, 1 worker.
- Container limits thực tế: `VERIFY_WITH_DOCKER_INSPECT`.

Do đó, thông số VM đã có evidence; chưa được coi thông số giới hạn container là đã xác minh.

### 2.2 PaaS

Contract validation:
- GET read: 3 trials, PASS.
- GET CPU: 2 trials, PASS.
- Writes executed: false.
- Equivalence checked: false.

OpenAPI reference và service evidence được lưu riêng trong thư mục `results/t3/`.

### 2.3 FaaS

Đã sửa và triển khai lại FaaS để phục vụ OpenAPI specification tại `/openapi.json`.

Evidence sau triển khai:
- Cloud Run service revision: `ccapi-faas-00003-fin`.
- Revision state: `ACTIVE`.
- Traffic: 100%.
- CPU: 1.
- Memory: 1 GiB.
- Timeout: 60 giây.
- Maximum instances: 10.
- Concurrency: 1.
- Runtime service account: `ccapi-api@ccapi-tran-2026.iam.gserviceaccount.com`.
- Invoker service account: `ccapi-benchmark-invoker@ccapi-tran-2026.iam.gserviceaccount.com`.
- OpenAPI endpoint: HTTP 200.
- OpenAPI paths được xác minh: `/compute`, `/health`, `/items`, `/items/{item_id}`.

Contract validation sau triển khai:
- GET read: 3 trials, PASS.
- GET CPU: 2 trials, PASS.
- Writes executed: false.
- Equivalence checked: false.

Các snapshot trước khi sửa được giữ lại để bảo toàn lịch sử thay đổi.

## 3. Billing và chi phí

Billing budget inventory chưa được xác minh đầy đủ do tài khoản thực thi không có đủ quyền truy cập billing account.

File `billing-budgets.json` hiện chứa `[]`, nhưng không sử dụng kết quả này để kết luận rằng billing account không có budget.

**Status: BLOCKED – INSUFFICIENT PERMISSIONS.**

Chưa có invoice reconciliation hoặc xác nhận chi phí thực tế từ billing export trong phạm vi evidence này.

## 4. Những gì đã hoàn thành

- [x] IaaS live contract validation.
- [x] PaaS live contract validation.
- [x] FaaS OpenAPI endpoint được triển khai và xác minh HTTP 200.
- [x] FaaS live contract validation sau triển khai.
- [x] Read và CPU endpoints được kiểm tra bằng GET.
- [x] Không thực hiện thao tác ghi dữ liệu trong contract validation.
- [x] Lưu evidence cấu hình và IAM liên quan đến FaaS.
- [x] Lưu OpenAPI reference và live OpenAPI snapshot.

## 5. Những việc chưa hoàn thành

| Hạng mục | Trạng thái | Evidence cần bổ sung |
|---|---|---|
| Kết quả dữ liệu tương đương giữa ba model | NOT VERIFIED | So sánh normalized payload trên cùng input và seed |
| IaaS container resource limits | NOT VERIFIED | Docker Inspect trên VM |
| Billing budgets | BLOCKED | Quyền đọc billing account |
| Invoice reconciliation | NOT VERIFIED | Billing export hoặc invoice |
| Benchmark hiệu năng REAL | NOT VERIFIED | Các run benchmark hợp lệ trên hạ tầng thật |
| Confirmed platform cold start | NOT VERIFIED | Platform logs liên kết request ID và instance |
| Autoscaling comparison | NOT VERIFIED | Runtime instance metrics và scaling evidence |

## 6. Phạm vi kết luận

T3 hiện có bằng chứng cho việc triển khai và xác minh contract của ba mô hình IaaS, PaaS và FaaS.

Không được suy rộng kết quả này thành:
- Ba nền tảng đã trả về dữ liệu tương đương.
- Một nền tảng nhanh hơn hoặc rẻ hơn nền tảng khác.
- Đã xác minh cold start ở cấp cloud platform.
- Đã xác minh autoscaling hoặc khả năng chịu tải.
- Đã xác minh tổng chi phí thực tế.

Các kết luận trên cần evidence riêng theo protocol benchmark.

## 7. Evidence files

- `results/t3/iaas-contract.json`
- `results/t3/paas-contract-verified-20261112.json`
- `results/t3/faas-contract-verified-20261112.json`
- `results/t3/faas-openapi-live-verified-20261112.json`
- `results/t3/paas-openapi-reference.json`
- `results/t3/iaas-resource-snapshot.json`
- `results/t3/faas-service-evidence.json`
- `results/t3/faas-deploy-config-before-fix.yaml`
- `results/t3/faas-run-config-before-fix.yaml`
- `results/t3/faas-iam-before-fix.json`
- `results/t3/faas-run-iam-before-fix.json`
- `results/t3/faas-iam-policy.json`
- `results/t3/paas-iam-policy.json`
- `results/t3/cloud-run-inventory.txt`
- `results/t3/cloud-functions-v2-inventory.json`
- `results/t3/enabled-apis.txt`
- `results/t3/project-quotas.json`
- `results/t3/regional-quotas.json`
- `results/t3/gcp-compute-quotas.json`

---
**Report classification:** Infrastructure and API contract evidence. Not a final performance or cost comparison.
