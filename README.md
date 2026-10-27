# cloud-api-compare (Đề tài 11: IaaS vs PaaS vs FaaS)

Một API, ba mô hình triển khai trên GCP (asia-southeast1).

## Cấu trúc và chủ sở hữu
| Thư mục | Chủ | Nội dung |
|---|---|---|
| contracts/ | Trân | openapi.yaml (sinh bằng scripts/export_openapi.py) |
| core/ | Trân | Logic dùng chung (ccapi_core), test |
| adapters/fastapi/ | Trân | Adapter IaaS + PaaS, Dockerfile |
| adapters/function/ | Lộc | Adapter Cloud Run functions |
| infra/shared, infra/iaas | Trân | Terraform |
| infra/paas, infra/faas | Lộc | Terraform |
| infra/loadgen, bench/ | Phúc Hoàng | VM tải, k6, kết quả |
| ops-log/ | Mỗi người | Nhật ký vận hành (mẫu: TEMPLATE.md) |

## Chạy local (không cần cloud)
    python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
    pip install -r adapters/fastapi/requirements.txt -r requirements-dev.txt
    pytest
    PYTHONPATH=core:adapters/fastapi uvicorn app:app --app-dir adapters/fastapi --port 8080
    # Windows PowerShell: $env:PYTHONPATH="core;adapters/fastapi"; uvicorn app:app --app-dir adapters/fastapi --port 8080

Thử: `curl localhost:8080/items/item-000001`, `curl "localhost:8080/compute?n=1000"`.

## Docker (đúng cấu hình đo: 1 vCPU, 1 GiB)
    docker build -f adapters/fastapi/Dockerfile --build-arg GIT_SHA=$(git rev-parse --short HEAD) -t ccapi:v1 .
    docker run --rm --cpus=1 --memory=1g -p 8080:8080 ccapi:v1

## Biến môi trường
STORE=memory|firestore (mặc định memory) · GCP_PROJECT · MODEL=iaas|paas|faas · GIT_SHA · SEED_COUNT (memory, mặc định 1000) · INSTANCE_ID (tùy chọn)

## Quy tắc (rút gọn, bản đầy đủ ở tài liệu kế hoạch mục 3)
- Không push thẳng main; PR nhỏ, review vòng tròn Trân -> Lộc -> Phúc Hoàng -> Trân.
- Không commit tfstate, khóa dịch vụ, .env.
- Đổi hợp đồng sau contract-v1 phải qua issue và cả 3 người đồng ý.
