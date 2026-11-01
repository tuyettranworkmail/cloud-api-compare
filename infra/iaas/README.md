# infra/iaas: VM Linux chạy API bằng Docker (mô hình IaaS)

Chủ sở hữu: Trân. State: bucket `ccapi-tfstate-<PROJECT_ID>`, prefix `iaas`.

## Tài nguyên được tạo
- VPC riêng `ccapi-iaas-vpc` + subnet `10.10.0.0/24` (asia-southeast1)
- Firewall: cổng 80 (API) và cổng 22 (chỉ qua IAP 35.235.240.0/20, cộng IP tùy chọn)
- IP tĩnh `ccapi-iaas-ip`
- VM `ccapi-iaas-api` (e2-standard-2, Ubuntu 24.04 LTS, đĩa 20 GB), service account `ccapi-api`
- Quyền cho service account: đọc Artifact Registry repo `ccapi`, ghi metrics
- Startup script (`startup.sh.tpl`): cài Docker (và Ops Agent), pull image, chạy container
  `--cpus=1 --memory=1g` với `MODEL=iaas STORE=firestore`

Ubuntu thường (không phải Container-Optimized OS) là lựa chọn có chủ đích: người vận hành tự
vá OS và tự cài Docker, đúng phần "trách nhiệm vận hành" mà đề tài cần đo.

## Trước khi apply: image phải có trong Artifact Registry
Ở thư mục gốc repo (thay PROJECT_ID):

    set PROJECT_ID=ccapi-tran-2026
    for /f %i in ('git rev-parse --short HEAD') do set SHA=%i
    docker build -f adapters/fastapi/Dockerfile --build-arg GIT_SHA=%SHA% -t ccapi:v1 .
    gcloud auth configure-docker asia-southeast1-docker.pkg.dev
    docker tag ccapi:v1 asia-southeast1-docker.pkg.dev/%PROJECT_ID%/ccapi/ccapi:v1
    docker push asia-southeast1-docker.pkg.dev/%PROJECT_ID%/ccapi/ccapi:v1

(Trong Git Bash dùng `SHA=$(git rev-parse --short HEAD)` và `$PROJECT_ID`.)

## Triển khai
    cd infra\iaas
    copy example.tfvars terraform.tfvars      (rồi sửa git_sha, project_id)
    terraform init -backend-config="bucket=ccapi-tfstate-%PROJECT_ID%"
    terraform plan -var-file=terraform.tfvars
    terraform apply -var-file=terraform.tfvars

Lần đầu VM cần 2 đến 4 phút để cài Docker và khởi động container sau khi `apply` xong.

## Kiểm tra
Dùng lệnh trong output `test_commands`, ví dụ `curl -i http://<IP>/items/item-000001`.
Phải thấy header `x-instance-id`, `x-cold-start`, `x-handler-ms`, và `"model": "iaas"` trong log.

SSH qua IAP (output `ssh_command`), rồi trên VM:

    sudo docker ps
    sudo docker logs ccapi --tail 5
    sudo docker inspect ccapi --format "CPU={{.HostConfig.NanoCpus}} MEM={{.HostConfig.Memory}}"
    sudo tail -50 /var/log/ccapi-startup.log

`inspect` phải ra `CPU=1000000000 MEM=1073741824`.

## Triển khai bản mới (đo "sửa lỗi đến phát hành" cho ops-log)
1. Build và push image với tag mới (ví dụ v2), 2. đổi `image_tag` và `git_sha` trong
`terraform.tfvars`, 3. `terraform apply`, 4. SSH vào VM, 5. `sudo google_metadata_script_runner startup`,
6. kiểm tra `git_sha` mới trong log. Ghi số bước và thời gian thật vào ops-log/tran.md.

Vá OS (cũng ghi vào ops-log): `sudo apt-get update && sudo apt-get upgrade -y`.

## Chi phí và dọn dẹp
VM tính tiền theo giờ khi chạy, và IP tĩnh tính tiền khi giữ. Đo xong thì:

    terraform destroy -var-file=terraform.tfvars

Chỉ tắt VM (không destroy) vẫn còn tính phí đĩa và IP tĩnh.

## Lưu ý
- Mặc định cổng 80 mở cho mọi IP. Khi đo chính thức, thu hẹp `http_source_ranges` về IP của
  nhóm và VM tải để tránh người lạ gọi vào API (có ghi vào Firestore).
- Nếu container không chạy: xem `/var/log/ccapi-startup.log` (thường do chưa push image
  hoặc service account chưa có quyền đọc Artifact Registry).
- `terraform.tfvars` đã bị .gitignore, đừng commit.

## Ảnh chụp cho báo cáo (mục 4.2)
Trang chi tiết VM (loại máy, vùng), firewall rule, kết quả `plan` và `apply`, `docker inspect`
trên VM, 3 endpoint gọi vào IP của VM thành công.
