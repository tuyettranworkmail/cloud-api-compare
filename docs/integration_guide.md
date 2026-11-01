# Tích hợp với phần của Tuyết Trân và Lộc

Toolkit không quản lý Terraform, image production, Firestore seed hoặc deployment. Các API và 100.000 seed records thuộc nhóm. `examples/mock_api.py` chỉ là fixture local để kiểm thử.

## Hợp đồng cần bàn giao

Tuyết Trân cung cấp OpenAPI, URL IaaS, VM name/ID/zone, Firestore location, dataset ID và danh sách seed ID tồn tại. Lộc cung cấp URL PaaS/FaaS, Cloud Run service name, function name, GEN_2, timeout, concurrency, min/max instances, memory, vCPU, billing mode và runtime thực.

`targets.yaml` là mapping chung. Đổi `read/write/cpu.path`, `method`, request body, expected status và JSON Schema theo API thật. Không sửa thuật toán CPU cho một model. CPU input phải cố định; preflight lặp input hai lần/model và so kết quả giữa ba model. GET kiểm tra toàn bộ `read_ids` đã cấu hình; không khẳng định kiểm tra cả 100.000 document nếu chỉ cung cấp vài ID. Schema OpenAPI và payload đã normalize phải khớp. Chỉ ignore các trường bất định có lý do, ví dụ ID POST tự sinh; không ignore result/value để che khác biệt nghiệp vụ.

Write payload dùng `{run_id}`, `{write_id}`. K6 sinh `bench-<run>-a<attempt>-<phase>-<iteration>`: không đụng seed đọc hoặc attempt khác. Adapter của nhóm phải ghi đúng namespace/collection riêng nếu quy trình yêu cầu. Không tự xóa record; cần quy trình cleanup có allowlist run ID, collection benchmark và kiểm tra quyền sở hữu. Toolkit hiện không có lệnh xóa tài nguyên/dữ liệu cloud.

## Middleware tối thiểu

Với FastAPI/ASGI của từng bản triển khai:

```python
from benchmark.instrumentation import BenchmarkMiddleware
app.add_middleware(BenchmarkMiddleware, deployment_model="paas")
```

Chọn `iaas`, `paas`, `faas` đúng deployment. Nếu API nằm ở repository khác, copy nguyên middleware cùng helper UTC (hoặc cài package toolkit) theo quy trình nhóm, không thay business logic. Middleware chuẩn ASGI nên dùng tại lớp ASGI trong adapter gen2; không gắn trực tiếp vào WSGI/Flask object. Chủ FaaS giữ adapter tương thích runtime của họ.

Headers: `X-Instance-ID` là UUID ngẫu nhiên tiến trình, không hostname/IP; `X-Cold-Start` là process-first-request; `X-Handler-Duration-Ms` đo đến response headers. Structured JSON logs chứa UTC, request_id, instance_id, model, endpoint, cold_start, handler_duration_ms và status_code. Log duration cuối request có thể dài hơn header đối với streaming; không so như cùng định nghĩa.

`X-Request-ID` do k6 gửi giúp join log chính xác. Trong Cloud Logging phải cấu hình logger/handler để JSON trở thành `jsonPayload` (ví dụ Google Cloud structured logging), thay vì JSON lồng trong textPayload. Toolkit không tự sửa cấu hình production logging. Middleware chỉ đánh dấu first **request bất kỳ**, nên preflight/health checks có thể sử dụng dấu first trước measurement. Không lấy cờ này làm bằng chứng khởi tạo hạ tầng.

Confirmed cold chỉ khi người thu thập có **sự kiện khởi tạo nền tảng độc lập** được liên kết với request/instance, và chuẩn hóa log có `platform_startup_confirmed: true`. Collector và k6 không tự tạo bằng chứng này. Các file DEMO có cờ đó được gắn SIMULATED. Idle sample zero không tự được nâng thành confirmed cold.

## Tài nguyên và công bằng

e2-standard-2 có full host 2 vCPU/8 GiB; app chuẩn hóa có thể chạy `--cpus=1 --memory=1g` theo quyết định của Tuyết Trân. Không áp dụng thay đổi này tự động trong toolkit. VM được thanh toán full host, dù app container giới hạn thấp hơn.

Thu bằng chứng Docker đọc từ VM hiện có:

```bash
python scripts/capture_container_limits.py --project YOUR_PROJECT --zone asia-southeast1-b --vm YOUR_VM --instance-id YOUR_NUMERIC_INSTANCE_ID --container YOUR_API_CONTAINER --output results/iaas_container_evidence.json
```

Điền `targets.iaas.runtime_evidence_file` bằng path output. Script chỉ đọc `.HostConfig`, chỉ lưu CPU limit/memory đã trích; không lưu env/secret Docker. Nếu không có CPU quota/cgroup evidence, controlled comparison bị từ chối. Workers/process count phải kiểm chứng riêng cùng nhóm. Evidence phải được thu lại sau mỗi thay đổi container; validator kiểm instance ID và giới hạn nhưng không thể chứng minh evidence file thủ công chưa bị sửa.

Cloud Run v2 service và functions v2 API được đọc bằng ADC trước run: resources, concurrency, template/service scaling, timeout, generation/revision, runtime gen2. Không tự thay cấu hình. Với `controlled`, runner yêu cầu CPU/RAM ứng dụng khớp và concurrency PaaS/FaaS khớp. Với `deployment`, khác biệt được ghi vào fairness.json và là confounders. Hai chế độ không được trộn thành một kết luận.

VM CPU là host metric, không bằng CPU container. Cloud Run utilization thường là distribution; collector giữ bucket boundaries để không biến mean thành p95. VM RAM qua Ops Agent là % host, không phải container RSS.

## Ops Agent cho RAM GCE

CPU GCE có sẵn `compute.googleapis.com/instance/cpu/utilization`, monitored resource `gce_instance`. RAM dùng `agent.googleapis.com/memory/percent_used`; cần Ops Agent hoạt động và service account có quyền ghi metrics. Việc cài agent do chủ VM thực hiện theo [tài liệu Google](https://cloud.google.com/monitoring/agent/ops-agent/installation). Kiểm tra receiver `hostmetrics` của agent và pipeline metrics, ví dụ cấu hình bổ sung theo cấu hình hiện có:

```yaml
metrics:
  receivers:
    hostmetrics:
      type: hostmetrics
      collection_interval: 60s
  service:
    pipelines:
      default_pipeline:
        receivers: [hostmetrics]
```

Merge cẩn thận với config agent đang dùng; toolkit không tự ghi `/etc/google-cloud-ops-agent/config.yaml`. Không cộng các state `free/cached/used/...` rồi gọi đó là RAM used; luôn đọc labels. Nếu thiếu agent, NO_DATA là thiếu dữ liệu, không phải RAM 0%.

## Authentication và proxy

Đặt token qua env; cần Run Invoker cho private Cloud Run/gen2. Không dùng user token trong YAML. Nếu gateway/proxy khác nhau, ghi vào `declared.gateway`; RTT/TLS path khác là confounder. Timeout và redirect policy giống nhau (không tự follow redirect). Chạy các model tuần tự vì dùng chung Firestore.
