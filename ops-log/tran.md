# Nhật ký vận hành – Trân
**Dự án:** Cloud API Compare – Đề tài 11 (IaaS, PaaS, FaaS)  
**Người thực hiện:** Nguyễn Hồ Tuyết Trân.  
**Vai trò:** Tech Lead – IaaS và hạ tầng dùng chung.  
**Thời gian ghi nhận:** 31/10/2026 – 01/11/2026.

> Lưu ý: Các thời lượng được ghi là ước lượng theo trí nhớ của người thực hiện. Thời gian trong ngày không được ghi nhận chính xác.

## [2026-10-31, giờ không xác định] chung — Tạo tài khoản Google Cloud và project
- Số bước thao tác: Chưa xác định chính xác.
- Thời gian thực tế (phút): 120 phút (ước lượng).
- Lỗi gặp phải và cách xử lý: Chưa ghi nhận lỗi cụ thể.
- Việc người vận hành phải tự quản: Quản lý tài khoản Billing, theo dõi credit dùng thử và kiểm soát chi phí phát sinh.
- Ghi chú: Tìm hiểu Google Cloud Platform, đăng ký tài khoản dùng thử, tạo project ccapi-tran-2026 và thiết lập Billing.

## [2026-10-31, giờ không xác định] chung — Thiết lập IAM và phân quyền
- Số bước thao tác: Chưa xác định chính xác.
- Thời gian thực tế (phút): 30 phút (ước lượng).
- Lỗi gặp phải và cách xử lý: Chưa ghi nhận lỗi cụ thể.
- Việc người vận hành phải tự quản: Quản lý quyền truy cập, đảm bảo phân quyền phù hợp cho các thành viên và Service Account.
- Ghi chú: Thiết lập IAM cho project ccapi-tran-2026, phân quyền Owner cho Trân, Editor cho Lộc và Phúc Hoàng, đồng thời cấu hình các quyền cần thiết cho Service Account.

## [2026-10-31, giờ không xác định] chung — Cài đặt và cấu hình công cụ phát triển
- Số bước thao tác: Chưa xác định chính xác.
- Thời gian thực tế (phút): 30 phút (ước lượng).
- Lỗi gặp phải và cách xử lý: Chưa ghi nhận lỗi cụ thể.
- Việc người vận hành phải tự quản: Quản lý phiên bản công cụ, cập nhật CLI và bảo mật thông tin xác thực.
- Ghi chú: Cài đặt Google Cloud CLI và Terraform 1.9.8 trên Windows 11, cấu hình môi trường PATH và đăng nhập Google Cloud bằng tài khoản Owner.

## [2026-10-31, giờ không xác định] chung — Seed dữ liệu thử nghiệm Firestore
- Số bước thao tác: Chưa xác định.
- Thời gian thực tế (phút): Không nhớ, chưa đủ dữ liệu để xác định.
- Lỗi gặp phải và cách xử lý: Chưa ghi nhận lỗi cụ thể.
- Việc người vận hành phải tự quản: Theo dõi tính toàn vẹn dữ liệu, kiểm tra số lượng document và đảm bảo dữ liệu thử nghiệm nhất quán.
- Ghi chú: Thực hiện seed dữ liệu vào collection items bằng scripts/seed_firestore.py. Cấu hình dữ liệu theo kế hoạch gồm 100.000 document, ID từ item-000001 đến item-100000, seed 42 và payload dài 512 ký tự. Chưa có bằng chứng xác nhận số lượng document thực tế đã tạo đầy đủ.

## [2026-10-31, giờ không xác định] chung — Build và chạy Docker API
- Số bước thao tác: Chưa xác định chính xác.
- Thời gian thực tế (phút): 60 phút (ước lượng).
- Lỗi gặp phải và cách xử lý: Chưa ghi nhận lỗi cụ thể.
- Việc người vận hành phải tự quản: Theo dõi trạng thái container, logs, mức sử dụng CPU/RAM và xử lý khi container dừng.
- Ghi chú: Build Docker image từ mã nguồn API, khởi chạy container ccapi và kiểm tra request GET /items/item-000001 trả về HTTP 200. Sử dụng docker logs, docker stats và docker inspect để kiểm tra hoạt động container và giới hạn tài nguyên 1 vCPU, 1 GiB RAM.

## [2026-11-01, giờ không xác định] chung — Triển khai hạ tầng dùng chung bằng Terraform
- Số bước thao tác: Chưa xác định chính xác.
- Thời gian thực tế (phút): 120 phút (ước lượng).
- Lỗi gặp phải và cách xử lý: Chưa ghi nhận lỗi cụ thể.
- Việc người vận hành phải tự quản: Theo dõi trạng thái tài nguyên cloud, quản lý Terraform state, IAM, mạng và chi phí tài nguyên.
- Ghi chú: Khởi tạo Terraform, kiểm tra cấu hình, thực hiện terraform plan và terraform apply cho thư mục infra/shared. Hoàn thành triển khai 15 tài nguyên hạ tầng dùng chung trên Google Cloud Platform.

## [2026-11-01, giờ không xác định] iaas — Xây dựng và kiểm tra cấu hình Terraform
- Số bước thao tác: Chưa xác định chính xác.
- Thời gian thực tế (phút): 120 phút (ước lượng).
- Lỗi gặp phải và cách xử lý: Không ghi nhận lỗi đáng kể. Terraform init và terraform plan thực hiện thành công.
- Việc người vận hành phải tự quản: Quản lý Terraform state, kiểm tra cấu hình mạng, firewall, IAM, IP tĩnh, VM và theo dõi chi phí tài nguyên.
- Ghi chú: Xây dựng cấu hình Terraform trong infra/iaas, khởi tạo backend GCS, tải Google provider và chạy terraform plan. Kết quả dự kiến 9 tài nguyên cần tạo (9 to add). Chưa thực hiện terraform apply.

## [2026-11-01, giờ không xác định] chung — Khôi phục mã nguồn sau sự cố Git
- Số bước thao tác: Chưa xác định chính xác.
- Thời gian thực tế (phút): 15 phút (ước lượng).
- Lỗi gặp phải và cách xử lý: PR #3 khiến các thư mục core, adapters, contracts và infra biến mất khỏi nhánh main do sử dụng git add -A trong thư mục làm việc thiếu file. Nhóm sử dụng lịch sử Git để khôi phục mã nguồn thông qua PR #4.
- Việc người vận hành phải tự quản: Kiểm tra git status, nội dung staged changes, kiểm tra các file bị xóa ngoài ý muốn trước khi commit và push.
- Ghi chú: Tham gia khôi phục mã nguồn bằng Git, giúp đưa các thư mục quan trọng trở lại nhánh main. Sau sự cố, nhóm bổ sung quy trình kiểm tra git diff --cached --name-status trước mỗi commit.

## [2026-11-03, giờ không xác định] iaas — Triển khai VM và xác minh API
- Số bước thao tác: 9 tài nguyên Terraform được tạo; sau đó thay thế 1 VM để sửa startup script.
- Thời gian thực tế (phút): Chưa ghi nhận chính xác.
- Lỗi gặp phải và cách xử lý: Lần khởi động đầu tiên thất bại vì file startup có xuống dòng Windows, khiến shebang `/bin/bash` không chạy trên Ubuntu. Đã chuẩn hóa xuống dòng sang Linux trong Terraform, tạo lại VM và xác nhận startup script hoàn tất.
- Việc người vận hành phải tự quản: Theo dõi state Terraform, log startup, container Docker, firewall, IP tĩnh và credit Free Trial.
- Ghi chú: Triển khai thành công VPC/subnet, firewall HTTP và SSH qua IAP, IP tĩnh `34.142.242.95`, VM `ccapi-iaas-api` (e2-standard-2, Ubuntu 24.04, disk 20 GB), quyền pull Artifact Registry và ghi metrics. Các endpoint `/health`, `/items/item-000001` và `/compute?n=1000` trả HTTP 200. Container `ccapi` chạy với CPU=1000000000 và MEM=1073741824. Log container có timestamp, endpoint, status, handler_ms và git_sha. Cổng 80 hiện mở `0.0.0.0/0`; cần thu hẹp về IP của nhóm và máy load test trước khi benchmark chính thức.

---

## Mẫu đo "sửa lỗi → phát hành"

- Thời điểm commit: Chưa ghi nhận.
- Thời điểm bản mới nhận request đầu tiên (xem log, git_sha mới): Chưa ghi nhận.
- Số bước thủ công ở giữa: Chưa đo lường.

**Ghi chú:** Sẽ tiếp tục cập nhật phần này khi triển khai và phát hành phiên bản API mới trên IaaS.

---

## Tổng kết tuần 1

- Tổng số nhóm công việc đã ghi nhận: 8.
- Tổng thời gian đã xác định: 495 phút (8 giờ 15 phút).
- Thời gian seed Firestore: Chưa xác định.
- Các thời lượng đã ghi nhận đều là ước lượng theo trí nhớ.
- Hạ tầng dùng chung đã triển khai thành công.
- Docker API đã build và chạy thử thành công.
- Cấu hình Terraform IaaS đã viết và plan thành công với 9 tài nguyên dự kiến tạo, chưa apply.
- Sự cố Git đã được khôi phục thông qua PR #4.

**Trách nhiệm vận hành chính của Trân:** Quản lý hạ tầng dùng chung, cấu hình và triển khai IaaS, quản lý Terraform state, IAM, mạng, firewall, VM, container, giám sát tài nguyên và kiểm soát chi phí Google Cloud.

## [2026-11-03] iaas — Build và push Docker image v1
- Commit nguồn: `6247976d31006a491c9d32e2d405b12be32750d4` (short SHA: `6247976`).
- Image URI: `asia-southeast1-docker.pkg.dev/ccapi-tran-2026/ccapi/ccapi:v1`.
- Digest: `sha256:9f8b7d073766a294a0e3feab89a9eba81fbcd012afaf6ffad313f02a54d3a937`.
- Kết quả: Build Docker image thành công; kiểm tra biến môi trường `GIT_SHA=6247976`, `PORT=8080`, `STORE=memory`; push image lên Artifact Registry thành công và xác minh tag `v1`.
- Cấu hình IaaS cục bộ: cập nhật `git_sha = "6247976"` và `image_tag = "v1"` trong `infra/iaas/terraform.tfvars`; giữ nguyên `project_id` và `http_source_ranges`.
- Việc người vận hành phải tự quản: Khởi động Docker Desktop, cấu hình xác thực Docker với Artifact Registry, build/tag/push image và xác minh digest trên Registry.
- Ghi chú: Đây là bước chuẩn bị image và cấu hình cho phiên bản mới. Chưa chạy `terraform apply`, chưa cập nhật VM đang hoạt động và chưa xác nhận request thực tế từ image `v1`.
