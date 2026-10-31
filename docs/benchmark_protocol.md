# Giao thức thực nghiệm

## Trước đo

1. Chốt Git commit, dependencies, API contract, dataset snapshot, CPU input và region. Xác minh một máy tạo tải riêng trong asia-southeast1.
2. Lưu VM capacity, container cgroups, vCPU/GiB, worker count, runtime, concurrency, min/max instances, timeout, billing mode, Firestore location và proxy/gateway. Collector đọc cấu hình thực; declared fields chỉ là khai báo.
3. Kiểm tra seed IDs tồn tại và payload cùng kích thước; write vào namespace run riêng. Xác minh quyền write và chính sách cleanup do nhóm thực hiện riêng.
4. Pilot low load: máy k6 CPU/RAM còn dư, network không bão hòa, VU đủ, quota Firestore/Cloud Run được review. `quota_verified` là xác nhận có căn cứ của người vận hành, không phải xác nhận tự động từ Service Quotas API.
5. Xác minh trần chi phí theo request và giờ, gồm VM tạo tải, VM API, idle/cooldown, writes và cleanup, telemetry/network. Dry-run không liên hệ cloud. Bounds thiếu hoặc tổng kế hoạch vượt giới hạn thì REAL bị chặn.

## Khối thí nghiệm

Mặc định mỗi cấu hình chính có 5 independent runs; tăng 10+ khi có ngân sách. Mỗi vòng/cấu hình shuffle thứ tự ba model bằng seed đã lưu. Không chạy song song trên Firestore chung. Warm-up 45s, steady measurement 180s, cooldown 45s. Thay các giá trị qua config khi pilot cho thấy cần, giữ giống nhau cho ba model.

Steady dùng constant-arrival-rate 5/20/50 request/s. Mixed 70% read, 20% write, 10% CPU là phân bố xác suất bằng hash xác định; realized mix có sai số hữu hạn. `--endpoint` đo thuần một endpoint. Arrival workload là open; throughput không được mặc định bằng rate yêu cầu. Xem [k6 arrival-rate](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/arrival-rate-vu-allocation/) cho allocation VU.

Burst dùng ramping-arrival-rate, baseline 10 RPS 60s, ramp 2s, hold 100 RPS 60s, down 2s, recovery 60s; giữ warm-up riêng. Offered volume tích phân hình thang qua ramps. Không gọi fixed IaaS VM là autoscaling. Cửa sổ latency và sample instance count có độ phân giải khác nhau.

Idle: kết thúc mọi app probe/preflight trước thời gian idle; không gọi endpoint “health check” trong khoảng nghỉ. Runner có thể đọc Monitoring API vì không tạo app request. Ghi idle_start/end; chờ 1.200s cấu hình được; request đầu rồi 20 warm requests. Idle không đảm bảo zero. Middleware first request, platform startup và Monitoring sampled-zero là ba loại bằng chứng khác nhau. IaaS luôn bật là baseline sau idle; reboot VM cần một experiment khác, không gộp với serverless cold start.

Warm-up và measurement là hai k6 scenarios riêng. Warm-up có gracefulStop 0 nên request còn chạy tại ranh giới có thể bị hủy và được gắn warmup; đã loại khỏi phân tích chính. Độ dài warm-up cần đủ để không mang hiệu ứng sang measurement; báo hạn chế này. Request measurement còn chạy được grace period, được lưu; throughput completions-in-window và cohort throughput được tách.

## Trong và sau đo

Runner giữ `runner.lock`, reserve ngân sách trước smoke writes, snapshot cấu hình, lưu metadata/hashes và ghi từng attempt. Config/auth token không được đưa vào metadata. Private runtime config tồn tại khi chạy k6 rồi được xóa trong finally. Không kill process runner để tránh mất trạng thái; Ctrl+C được ghi INTERRUPTED. Kill cưỡng bức có thể để lock/private file: kiểm tra, xử lý thủ công và giữ reservation bảo thủ.

Generator CPU/memory sampled mỗi giây là whole-VM metric. Vượt ngưỡng hoặc dropped iterations => invalid; network saturation có thể tồn tại dù CPU thấp. k6 threshold error 25% abort sau 15s nhằm hạn chế tiếp tục gửi tải khi API lỗi nặng. Threshold không phải SLA cuối nghiên cứu. Config budget không tự bảo đảm hóa đơn toàn tài khoản khi tài nguyên khác vẫn chạy.

Monitoring thường sampled 60s, có thể trễ hiển thị 120s; runner chờ 180s để thu sau run. Raw giữ distribution, labels, intervals. Có thể cần collect lại muộn hơn. Empty/error metric giữ nguyên trạng thái; không tạo sample giả. Các thông số này cần kiểm tra ở [metric registry chính thức](https://docs.cloud.google.com/monitoring/api/metrics_gcp_p_z) vì từng metric có lịch khác nhau.

Phân tích chỉ copy raw, validate timestamps UTC, giữ request lỗi/outliers, quarantine invalid/conflicting duplicates. CI được tính từ các run hợp lệ độc lập; không dùng hàng nghìn request trong một run như hàng nghìn replicate. P99 thiếu ổn định với ít mẫu và phải nêu rõ.

## Báo cáo thí nghiệm

Luôn kèm mode, UTC/date, seed, Git SHA hoặc source hashes, config thực tế, dataset ID, run count, valid/invalid reasons, bootstrap method, đơn vị, phần thiếu và threats to validity. So sánh model chỉ trong cùng scenario/level/endpoint/configuration mode. Fixed 1-VM cost được đánh dấu khi chưa chứng minh capacity. Không suy ra service model là nguyên nhân duy nhất khi phần cứng/concurrency khác nhau.
