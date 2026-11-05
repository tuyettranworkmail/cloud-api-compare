# Nhật ký vận hành — Lộc

**Đề tài:** So sánh thực nghiệm IaaS, PaaS và FaaS cho cùng một API  
**Người thực hiện:** Lộc  
**Phạm vi:** PaaS (Cloud Run) và FaaS (Cloud Run functions)  
**Google Cloud Project:** `ccapi-tran-2026`  
**Vùng triển khai:** `asia-southeast1`

## 2026-11-02 — Triển khai thử nghiệm FaaS

- Hoàn thiện và đóng gói mã nguồn FaaS thành `ccapi-faas-source.zip`.
- Tạo bucket `ccapi-faas-source-loc-2026` và upload ZIP.
- Khởi tạo Terraform backend, kiểm tra `terraform validate` và `terraform plan`.
- Triển khai Cloud Run functions thành công bằng `terraform apply`.
- Thời gian Terraform tạo Function: khoảng **1 phút 6 giây**.
- Kiểm thử `GET /health`, `GET /compute`, `GET /items/{id}`: thành công.
- Kiểm thử `POST /items`: lần đầu HTTP 201, gửi trùng HTTP 200.
- Cấu hình: Python 3.12, 1 vCPU, 1 GiB RAM, min instances 0, max instances 10.

**Ghi chú:** Đây là bản triển khai thử. Giá trị `GIT_SHA` đang là `dev`, cần đồng bộ theo phiên bản chính thức trước benchmark.

## 2026-11-02 — Triển khai thử nghiệm PaaS

- Build Docker image bằng `adapters/fastapi/Dockerfile`.
- Kiểm thử container trên laptop: HTTP 200.
- Upload image với tag `loc-temp-20261102` lên Artifact Registry.
- Cấu hình và triển khai Cloud Run bằng Terraform.
- Thời gian Terraform tạo dịch vụ: khoảng **22 giây**.
- Kiểm thử `GET /health`, `GET /compute`, `GET /items/{id}`: thành công.
- Kiểm thử `POST /items`: lần đầu HTTP 201, gửi trùng HTTP 200.
- Cấu hình: 1 vCPU, 1 GiB RAM, min instances 0, max instances 10.

**Ghi chú:** Image tạm chỉ phục vụ kiểm thử quy trình triển khai, chưa dùng benchmark chính thức.

## 2026-11-03 — Đồng bộ nhóm

- Cập nhật nhánh `main` lên commit `5031545`.
- Xác nhận Terraform FaaS đã được merge thông qua PR #7.
- Kiểm tra Artifact Registry: chưa thấy tag image chính thức trong danh sách.
- Chờ image và Git SHA cuối của Trân để cập nhật PaaS và FaaS.

## Việc cần hoàn thiện

- Đồng bộ hai mô hình với phiên bản mã nguồn cuối.
- Chạy contract test trên cả hai URL sau khi cập nhật.
- Xác minh CPU, concurrency và gửi thông số cho Phúc Hoàng.
- Ghi thời gian thực tế của quy trình sửa lỗi đến phát hành.
- Lưu ảnh minh chứng và hoàn thiện nhật ký vận hành.

## 2026-11-03 — Triển khai phiên bản chính thức

- **PaaS:** Cập nhật Docker image `v1`, Git SHA `6247976`. Terraform apply thành công trong 22 giây.
- **FaaS:** Cập nhật ZIP mã nguồn và Git SHA `6247976`. Terraform apply thành công trong 1 phút 13 giây.
- **Kiểm thử:** Cả hai API trả HTTP 200 tại `/health`, `/compute?n=1000` và `/items/item-000001`. Kết quả digest giống nhau.
- **Cấu hình PaaS:** 1 vCPU, 1 GiB RAM, concurrency 80, min 0, max 10.
- **Cấu hình FaaS:** 1 vCPU, 1 GiB RAM, concurrency 1, min 0, max 10.
- **Bàn giao:** Đã gửi hai URL và thông số cấu hình cho Phuc để thực hiện Contract Test và Pilot Test.
- **Ghi chú:** API yêu cầu xác thực bằng Google Cloud identity token.

## 2026-11-04 — Xác minh cấu hình và chuẩn bị đo vận hành

- Kiểm tra `terraform plan` cho PaaS và FaaS: cả hai đều báo `No changes`.
- Lưu cấu hình triển khai thực tế vào hai file `paas-config.txt` và `faas-config.txt`.
- Đối chiếu thời gian cập nhật phiên bản ngày 03/11: PaaS 22 giây; FaaS 73 giây.
- Chưa đo đầy đủ thời gian từ sửa mã nguồn đến phát hành.
- Chưa có kết quả xác nhận Contract Test và Pilot Test từ Phuc.
- Giữ nguyên cấu hình để phục vụ các phép đo tiếp theo.

## 2026-11-05 — Đo vận hành PaaS và FaaS

### PaaS

- Docker build: 31,11 giây.
- Docker push lên Artifact Registry: 13,76 giây.
- Terraform apply cập nhật phiên bản ngày 03/11: 22 giây.

### FaaS

- Chuẩn bị mã nguồn và tạo ZIP: 3,95 giây.
- Upload ZIP lên Cloud Storage: 15,41 giây.
- Terraform apply cập nhật phiên bản ngày 03/11: 73 giây.

### Ghi chú

- Các bước đóng gói và tải lên được đo ngày 05/11.
- Thời gian Terraform apply lấy từ lần triển khai thực tế ngày 03/11.
- Chưa đo đầy đủ thời gian sửa mã nguồn đến phát hành.
- PaaS có thể sử dụng cache Docker và các layer đã tồn tại trên Registry.
- Chưa triển khai lại dịch vụ đang chạy để tránh ảnh hưởng benchmark.
- Vẫn cần tổng kết số bước thao tác và công việc người vận hành phải tự quản lý.
