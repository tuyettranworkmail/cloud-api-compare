# CCAPI — Terraform FaaS

## Mục đích

Chuẩn bị hạ tầng Cloud Run functions thế hệ 2 trên Google Cloud bằng Terraform.

## Cấu hình

- Provider: Google Cloud
- Region: asia-southeast1 (Singapore)
- Runtime: Python 3.12
- Entry point: ccapi
- CPU: 1 vCPU
- RAM: 1 GiB
- Timeout: 60 giây
- Min instances: 0
- Max instances: 10
- Store dự kiến: Firestore

## Kiểm tra cấu hình

Chạy từ thư mục gốc repository:

    terraform -chdir=infra/faas fmt
    terraform -chdir=infra/faas init -backend=false
    terraform -chdir=infra/faas validate

## Điều kiện triển khai

Cần xác nhận với Trân:

- GCS bucket chứa mã nguồn FaaS
- Tên ZIP source object
- Service account và quyền Firestore
- GCS bucket lưu Terraform state
- Quyền truy cập HTTP Function

## Trạng thái

- Terraform init: Thành công
- Terraform validate: Thành công
- Chưa terraform apply
- Chưa triển khai lên GCP
- Chưa chạy contract test trên Cloud

## Phụ trách

Lộc — infra/faas/
