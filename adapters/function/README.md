# CCAPI — FaaS Adapter

## 1. Mục đích

Triển khai cùng logic nghiệp vụ của CCAPI dưới dạng HTTP Function bằng Python và Functions Framework.

Adapter tái sử dụng thư viện `ccapi_core` của dự án, không viết lại logic nghiệp vụ.

## 2. Công nghệ

- Python 3.12
- Functions Framework 3.10.2
- Flask
- Google Cloud Firestore (thư viện đã khai báo)
- Cloud Run functions (nền tảng triển khai dự kiến)

## 3. Các endpoint

| Method | Endpoint         | Chức năng           |
| ------ | ---------------- | ------------------- |
| GET    | /health          | Kiểm tra trạng thái |
| GET    | /compute?n=1     | Xử lý CPU           |
| GET    | /items/{item_id} | Đọc bản ghi         |
| POST   | /items           | Tạo bản ghi         |

POST /items hỗ trợ Idempotency-Key để xử lý yêu cầu lặp.

## 4. Cách chạy local

Thực hiện từ thư mục gốc repository, với môi trường Python 3.12 đã cài dependencies.

PowerShell:

    $env:PYTHONPATH = (Resolve-Path .\core).Path
    $env:STORE = "memory"
    .\.venv\Scripts\functions-framework.exe --target=ccapi --source=adapters/function/main.py --port=8080

Truy cập:

    http://127.0.0.1:8080/health

MemoryStore chỉ phục vụ kiểm thử local, không phải cơ sở dữ liệu lưu trữ lâu dài.

## 5. Giám sát

Adapter trả về ba HTTP headers:

- X-Instance-Id
- X-Cold-Start
- X-Handler-Ms

Đồng thời ghi log JSON với instance_id, cold, endpoint, status, handler_ms và git_sha.

Cờ cold đánh dấu request đầu tiên trong tiến trình, không đo toàn bộ thời gian cold start của hạ tầng Cloud.

## 6. Kết quả kiểm thử

Đã kiểm thử local:

- GET /health
- GET /compute
- GET /items/{item_id}
- POST /items
- Chống ghi trùng bằng Idempotency-Key
- HTTP 404, 405 và 422
- Response headers và JSON logs

Đã kiểm thử bản đóng gói thử trên cổng 8081:

- GET /health
- GET /compute?n=1

## 7. Đóng gói và triển khai

Thư viện `ccapi_core` nằm trong thư mục `core/` của repository.

### 7.1. Đóng gói FaaS tự động

Từ thư mục gốc repository, chạy lệnh:

    .\adapters\function\build-package.ps1

Script thực hiện:

1. Tạo thư mục mới trong TEMP của Windows.
2. Sao chép main.py và requirements.txt.
3. Sao chép thư viện ccapi_core từ core/ của dự án.
4. Hiển thị đường dẫn và cấu trúc gói.

Script không chỉnh sửa mã nguồn gốc và không tự triển khai lên Google Cloud.

### 7.2. Kết quả kiểm thử

- Adapter FaaS: Đã vượt qua kiểm thử chức năng cơ bản trên local.
- Gói thử thủ công: GET /health và GET /compute hoạt động.
- Script build-package.ps1: Đã chạy và tạo các file dự kiến.
- Gói do script tạo: Chưa kiểm thử chạy độc lập.
- Cloud Run functions: Chưa triển khai thực tế.

### 7.3. Giới hạn hiện tại

- Chưa kiểm thử đầy đủ toàn bộ gói triển khai.
- Chưa triển khai FaaS lên Google Cloud.
- Chưa kiểm thử kết nối Firestore thực tế.
- Chưa thực hiện benchmark trên GCP.

## 8. Phạm vi phụ trách

Người phụ trách: Lộc.

Thư mục: adapters/function/
