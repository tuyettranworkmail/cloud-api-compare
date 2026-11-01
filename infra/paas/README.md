# CCAPI — PaaS Cloud Run

## Mục đích

Triển khai core API chung của nhóm trên Google Cloud Run
bằng Terraform.

## Cấu hình

- Provider: Google Cloud
- Project: ccapi-tran-2026
- Region: asia-southeast1 (Singapore)
- CPU: 1 vCPU
- RAM: 1 GiB
- Min instances: 0
- Max instances: 10
- Container image: Sử dụng image chung của Trân

## Kiểm tra Terraform

Chạy từ thư mục gốc repository:

    terraform -chdir=infra/paas fmt
    terraform -chdir=infra/paas init -backend=false
    terraform -chdir=infra/paas validate

## Trạng thái

- Đã tạo main.tf
- Terraform validate thành công
- Chưa thực hiện terraform apply
- Chưa triển khai Cloud Run thực tế

## Điều kiện cần trước khi triển khai

- Xác nhận đường dẫn container image
- Xác nhận service account và quyền Firestore
- Cấu hình GCS backend bucket
- Kiểm tra quyền truy cập dịch vụ Cloud Run

## Phụ trách

Lộc — infra/paas/
