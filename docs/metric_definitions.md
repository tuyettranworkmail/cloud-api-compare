# Định nghĩa chỉ số và công thức

## Request-level

| Trường | Đơn vị / định nghĩa |
|---|---|
| `latency_ms` / `http_req_duration` | ms; sending + waiting + receiving của k6; không gồm toàn bộ setup kết nối |
| `http_req_waiting` | ms; time to first byte |
| blocked / connecting / tls_handshaking | ms; các giai đoạn riêng, giữ raw, không cộng tùy tiện khi tái sử dụng kết nối |
| `wall_ms` | ms; thời gian quanh lệnh http.request; có setup, blocking và overhead client |
| `handler_ms` | ms theo middleware, không phải CPU execution seconds |
| `status` | HTTP status; 0 biểu thị transport error khi k6 không nhận HTTP response |
| `success` | expected status + JSON/required fields + optional business-success predicate |
| `classification` | confirmed_cold / application_first_request / confirmed_warm / unknown |
| `request_id` | join key do client sinh; gồm run, attempt, phase và iteration |
| `scenario_start_ms` | epoch milliseconds UTC của k6 scenario; xác định cửa sổ đo |

Full JSON Schema và normalized payload được kiểm tra preflight. Trong load test, để giới hạn overhead máy phát, kiểm required fields và predicate thay vì chạy full JSON Schema cho mỗi request. Schema/phức tạp nghiệp vụ bổ sung cần adapter/check phù hợp ở nhóm. Built-in `http_req_failed` theo định nghĩa k6 không thay thế business error rate của toolkit.

Khuyến nghị JSONL để giữ timestamp chính xác. Native CSV mặc định timestamp unix seconds; nếu cần time-series chính xác hơn, chọn `K6_CSV_TIME_FORMAT=rfc3339_nano`. Với CSV unix_milli/micro/nano, metadata cần `csv_time_unit: ms/us/ns`. Parser đọc custom `extra_tags` dạng URL-encoded hoặc JSON. Pipeline cross-run chỉ giữ scheduling counters/gauges trong RAM, còn toàn bộ k6 timing metrics vẫn nằm trong raw bất biến.

## Run-level

Cho N request hợp lệ về định dạng, S success, F failure, U unknown outcome, T measurement seconds:

- N = S + F + U. Latency tổng thể dùng cả success và failure. Dữ liệu invalid được quarantine và làm run không hợp lệ, không biến thành latency 0.
- Mean = Σlatency/N. Sample SD = sqrt(Σ(x−mean)²/(N−1)). CV = SD/mean nếu mean > 0.
- P50/P95/P99 = `numpy.quantile(..., method='linear')`, không là trung bình của percentile các endpoint.
- Achieved RPS = số request thuộc cohort measurement hoàn thành trong cửa sổ T / T. Request kết thúc trong graceful stop ngoài T được giữ riêng trong **cohort RPS = N/T**.
- Goodput RPS = S/T của cohort (có thể gồm completion trong grace); không đồng nghĩa achieved throughput thành công theo completion window.
- Error rate (%) = 100F/N; U được báo riêng, không coi là success. Zero-request error rate là thiếu/NaN, không là 0%.
- Offered RPS = tích phân rate trong measurement / T. Endpoint offered RPS dùng tỷ lệ mục tiêu; realized mix có sai số.
- Dropped (%) = 100 × dropped_measurement / offered_measurement. Native dropped points lấy tag scenario để bỏ warmup.
- Cold ratio (%) = confirmed_cold/N. Application-first và unknown không được đếm thành confirmed cold.

Idle là closed sequential probe, không có offered arrival-rate cố định; offered_rps = N/A. Throughput idle dùng elapsed từ request đầu đến completion cuối và chỉ mang tính mô tả, không là khả năng chịu tải.

## Between-run CI

Với k run độc lập trong cùng model/scenario/endpoint/load, tính metric θᵢ từng run. Estimate = mean(θ₁…θₖ). Bootstrap B=2.000 lần lấy lại k run có hoàn lại, tính mean mỗi lần; CI = quantile 2,5% và 97,5% của các bootstrap means. Seed được lưu. `number_of_runs`, `sample_size`, method, estimate, lower, upper luôn xuất.

Không phải CI của percentile dữ liệu request gộp; request không được coi độc lập giữa các lượt trong cùng run. K<2 không có CI; K<5 báo FEW_RUNS. P99/run với N<1.000 có cờ bất ổn. Cold/warm per-group chỉ xuất p95 khi >=20 sample và p99 khi >=1.000, vẫn phải thận trọng về đuôi.

## Cold/warm và scaling

Cold penalty mô tả = trung bình giữa run của (median confirmed-cold − median confirmed-warm) cùng endpoint; ít nhất 1 cold và 5 warm/run và 5 paired runs để báo CI. Không trừ handler time khỏi client latency rồi gọi đó là network/cold overhead. Hai phân phối có thể khác load, instance placement hoặc queueing; đây là association.

Scale-out: xác định burst start từ measurement start + baseline duration. Lấy baseline instance sample trước burst, tìm sample tăng đầu tiên. Sự kiện tăng nằm trong khoảng [sample trước, sample tăng], cắt dưới tại burst start để báo phản ứng quan sát. Tăng đã xảy ra giữa sample trước và burst có thể là confounder; không chứng minh quan hệ nhân quả. Report lower/upper seconds, sampling, observed/peak timestamps. Fixed VM = NOT_APPLICABLE, missing monitoring = INSUFFICIENT_DATA, không quan sát tăng = NO_SCALE_OBSERVED.

Burst onset: bin 10s sau burst, p95 > 1,5×baseline p95; mỗi bin tối thiểu 20 sample. Recovery cần hai bin liên tiếp p95 <= ngưỡng. Đây là ngưỡng phân tích khai báo, không là định nghĩa dịch vụ. `burst_phases.csv` dùng request initiation để tách baseline/ramp_up/hold/ramp_down/recovery; `timeline.csv` dùng completion bins và có thể cắt ranh giới phase.

## Cloud Monitoring

| Nguồn | Resource | Metric |
|---|---|---|
| GCE host CPU | gce_instance | compute.googleapis.com/instance/cpu/utilization |
| GCE host RAM (agent) | gce_instance | agent.googleapis.com/memory/percent_used |
| GCE uptime | gce_instance | compute.googleapis.com/instance/uptime |
| Run/gen2 instances | cloud_run_revision | run.googleapis.com/container/instance_count |
| Run startup | cloud_run_revision | run.googleapis.com/container/startup_latencies |
| Run CPU / memory | cloud_run_revision | run.googleapis.com/container/cpu/utilizations; container/memory/utilizations |
| Run request duration/count | cloud_run_revision | run.googleapis.com/request_latencies; request_count |
| Run active billable time | cloud_run_revision | run.googleapis.com/container/billable_instance_time |

Raw distribution mean/count/buckets được giữ. Bảng processed scalar `value` là mean đối với distribution, **không phải p95**. Count cộng active+idle/all revisions cùng timestamp; nếu một state/revision bị thiếu series, tổng chỉ là observed total, không chứng minh tổng chính xác. Không nội suy sub-minute. Không cộng utilization labels hoặc distribution mean tùy ý.

Các fractional CPU/memory metric và agent memory percent có đơn vị khác nhau; xem raw unit/descriptor. `billable_instance_time` là aggregate active/start billable seconds; không thay thế toàn bộ lifecycle seconds của instance-based billing.
