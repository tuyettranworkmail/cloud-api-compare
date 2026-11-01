# Mô hình chi phí và giả định

## Nguồn giá và phạm vi

Giá public on-demand USD, không Spot/CUD, chưa thuế, region Singapore `asia-southeast1`. Catalog tra ngày **31/10/2026**. `effective_date` chưa được API xác minh được giữ `null`; đây không phải giá hợp đồng hay hóa đơn của tài khoản. Numeric SKU ID không có trong bảng public được giữ `null`, còn `sku` là mô tả chính thức của tài nguyên.

| Thành phần | Giá trong snapshot | Nguồn |
|---|---:|---|
| e2-standard-2 Linux | 0,08266614 USD/VM-hour | [Compute Engine](https://cloud.google.com/products/compute/pricing/general-purpose) |
| Standard zonal PD Singapore | 0,044 USD/GiB-month | [Disk pricing](https://cloud.google.com/compute/disks-image-pricing) |
| Run request active CPU | 0,0000336 USD/vCPU-second | [Cloud Run](https://cloud.google.com/run/pricing) |
| Run request active RAM | 0,0000035 USD/GiB-second | [Cloud Run](https://cloud.google.com/run/pricing) |
| Run request idle min CPU/RAM | mỗi loại 0,0000035 USD/unit-second | [Cloud Run](https://cloud.google.com/run/pricing) |
| Run instance CPU | 0,0000216 USD/vCPU-second | [Cloud Run](https://cloud.google.com/run/pricing) |
| Run instance RAM | 0,0000024 USD/GiB-second | [Cloud Run](https://cloud.google.com/run/pricing) |
| Run requests | 0,40 USD/triệu request | [Cloud Run](https://cloud.google.com/run/pricing) |
| Firestore document reads | 0,0369 USD/100.000 | [Firestore Standard](https://cloud.google.com/firestore/pricing) |
| Firestore document writes | 0,1107 USD/100.000 | [Firestore Standard](https://cloud.google.com/firestore/pricing) |
| Firestore deletes | 0,0123 USD/100.000 | [Firestore Standard](https://cloud.google.com/firestore/pricing) |
| Firestore storage | 0,1846 USD/GiB-month | [Firestore Standard](https://cloud.google.com/firestore/pricing) |

Bằng chứng trích đúng bảng **Singapore**, không phải bảng mặc định Iowa, nằm trong `reports/sources/*_singapore_tables.json`; HTML gốc nén `.html.gz`, URL/ngày/hash trong `source_manifest.json`. Đặc biệt không suy giá instance billing bằng cách áp tỷ lệ request billing: bảng Singapore instance CPU trong snapshot là 0,0000216, không tự gán 0,0000252 theo suy luận tier.

Cloud Run source/function deployment chạy như Run service và được tính theo cấu hình Run; build/artifact/event delivery có thể tính riêng. Không dùng bảng Functions gen1 cho gen2. Xem [nguồn Cloud Run](https://cloud.google.com/run/pricing) và [so sánh functions](https://docs.cloud.google.com/run/docs/functions/comparison).

Các SKU route-dependent egress, IP, build machine, Logging/Monitoring và Artifact chưa được chọn trong workload mặc định. Giá `null` là **cần cập nhật**, không có nghĩa miễn phí. Quantity 0 không tính khoản đó; quantity dương khi thiếu giá sẽ báo `PriceMissingError`. Với workload internet, nhập đúng destination/network tier và các price tiers phù hợp; model rate đơn không tự mô phỏng mọi tier mạng lớn. Phí backup/PITR/optional/auxiliary có thể nhập USD riêng; nguồn phải ghi cùng giả định.

`scripts/snapshot_prices.py` tải bản chụp public và trích bảng vùng; không tự overwrite catalog. Nếu Google đổi format, output báo cần review. `scripts/export_billing_catalog.py` đọc SKU API bằng ADC, giữ effective_time, usage_unit, conversion factor, tiered rates; người vận hành map đúng SKU/region/billing mode, không chọn theo giá thấp nhất.

## IaaS

Compute = VM_count × VM_hours × full VM hourly price. Mặc định 730h, tương ứng quy ước tháng tính giá phổ biến, không ép mọi tháng lịch bằng 730h. Disk và IP thêm riêng; container limit 1 vCPU/1 GiB không giảm giá VM 2 vCPU/8 GiB.

Total còn gồm egress, telemetry, backup, artifact/build, auxiliary, labor và Firestore. Capacity thực cần pilot tại SLA. `capacity_rps: null` → UNVERIFIED. Peak vượt capacity × count → UNSUPPORTED_CAPACITY. Không tự scale VM hoặc tuyên bố một VM luôn đủ. Có thể nhập số VM cố định khác nếu nhóm có triển khai tương ứng; toolkit không provision.

## PaaS/FaaS: request-based

Không dùng N×p95. Mỗi endpoint có mean **service/wall demand** và mean **CPU demand** khai báo riêng. Handler wall time không thay CPU seconds. Traffic được phân vào bins giờ theo uniform/business/bursty; cùng N có thể có overlap và số instance active khác nhau.

Ước tính occupancy dùng Poisson offered load L = RPS × rounded mean duration và giả định packing hoàn hảo theo concurrency c:

`E[busy instances] = Σ(k>=0) P(Poisson(L) > k*c)`.

Không chia toàn bộ thời gian request cho configured concurrency khi tải thưa. Đồng thời áp CPU floor = RPS × mean_CPU_seconds / (allocated_vCPU × target_utilization). Active demand lấy max của hai ước tính. Đây là mô hình gần đúng, không mô phỏng chính xác scheduler/autoscaler/queueing. CPU-bound workload có thể không đạt concurrency danh nghĩa và cần calibration.

Billable active seconds = tích phân busy instances theo thời gian + startup_count × ceil((startup+shutdown)/0,1)×0,1. Mean service được làm tròn 100ms như xấp xỉ bảo thủ của các busy intervals; billing thật làm tròn interval aggregate, không nhất thiết từng request. Với distribution CPU-bound/overlap thực tế, cần dữ liệu billable instance-time thay giả định. Startup CPU boost hay nhiều container có thể làm allocation thay đổi; model một container/CPU cố định chưa mô phỏng đầy đủ, phải điều chỉnh input/line item nếu dùng các tính năng đó.

Idle min seconds = tích phân max(min_instances − busy_instances, 0)dt. CPU active/idle và RAM active/idle có giá riêng. Request charge tính theo requests đủ điều kiện tới container; IAM rejection không nên được giả định như request billable giống nhau. Model nhận monthly volume đã định nghĩa, không cố đoán billing từ status code client.

`measured_active_instance_seconds` nhận số đo cho **đúng kỳ và volume**. Nó không được tự nhân sang volume khác. Cost report traffic curve/sensitivity sẽ từ chối fixed measured seconds để tránh dùng một thời gian đo cho mọi N. Muốn đo trực tiếp, gọi `CostModel.estimate` với số đo đúng hoặc tạo mô hình usage-vs-volume đã hiệu chỉnh.

## Instance-based

CPU/RAM tính toàn bộ lifetime. Estimator dùng số instance provisioned từ ceil busy demand trong mỗi bin giờ, min instances, startup, scale-down tail và minimum lifetime 60s cho giả định khởi động. Đây là ước tính ở độ phân giải giờ; burst ngắn có thể làm sai lệch. `measured_lifetime_instance_seconds` được ưu tiên nếu đúng scope. Không dùng active `billable_instance_time` thay cho lifetime khi billing theo instance. Không thêm request charge ở chế độ này.

PaaS/FaaS có cùng allocation/profile/billing nhận cùng chi phí; không ép tạo chênh lệch để có biểu đồ khác nhau.

## Firestore và các khoản dùng chung

Reads = requests/day × read_ratio × (reads/get + index_read_batches/get) × retry_multiplier. Writes = requests/day × write_ratio × writes/post × retry_multiplier. Deletes có input riêng. Index input là **số billing read batches/query đã xác minh**, không tự coi một index entry là một read; vector và query thường có quy tắc khác nhau. Model không tính lại query planner.

Storage gồm document, metadata/index overhead do người vận hành nhập, không suy từ số request. Network/optional features có input riêng. Retry multiplier có thể override theo từng `models.<model>.firestore_retry_multiplier`; nếu một model retry nhiều hơn phải dùng dữ liệu riêng.

Xuất `total_usd`, `compute_usd`, `shared_data_usd`, `without_shared_usd` và `cost_per_million_usd`. Zero requests → unit cost N/A; VM/min instances/storage vẫn có thể tốn tiền.

## Free tier

Mặc định tắt để so giá gross rõ ràng. Bật đòi `free_tier_eligible: true`, phạm vi `mutually_exclusive_alternatives` và `free_tier_remaining_fraction` theo billing account. Đây là so sánh nếu chọn một phương án; **không phải** tổng free tier cho ba dịch vụ cùng chạy.

Run free tier là spending discount theo Tier 1 prices. Request CPU credit 180.000×0,000024 = 4,32 USD; RAM 360.000×0,0000025 = 0,90 USD. Instance CPU 240.000×0,000018 = 4,32 USD, RAM 450.000×0,000002 = 0,90 USD. Vì Singapore có giá khác, không trừ 180.000 CPU-seconds Singapore như cùng đơn giá. Requests có 2 triệu allowance, áp dụng một lần theo phạm vi đã chọn. Nếu account có mixed billing modes/other services, cần phân bổ credit hợp lệ hoặc tắt tính năng đơn giản này.

Firestore free quota chỉ dùng khi `firestore_free_eligible` đã xác nhận database phù hợp. Reads 50.000/ngày, writes/deletes 20.000/ngày, storage 1 GiB. Model áp allowance theo **từng ngày**, không gộp 30 ngày để triệt tiêu burst một ngày. Ngày billing reset theo Pacific time; với dữ liệu thật nên cung cấp daily usage đã quy về biên quota tương ứng. Default model dùng đại diện các ngày, không đồng bộ lịch daylight saving từng tháng. Không tự áp miễn phí cho TTL/PITR/backup.

## Break-even và sensitivity

Tìm mọi sign-change trên log grid hữu hạn + breakpoints người dùng biết; giải Brent và kiểm residual. Equality trên các nodes và midpoint thành interval; sign jump với residual khác 0 là discontinuity, không là nghiệm. Không có giao điểm → NO_INTERSECTION_IN_DOMAIN; hai cấu hình bằng nhau → COINCIDENT_INTERVAL. Tìm kiếm hữu hạn có thể bỏ sót tangent/narrow intervals; với mô hình bậc phức tạp cần cung cấp đầy đủ breakpoints và review đường cong. Không khẳng định có/không có nghiệm ngoài miền đã xét.

Root details lưu capacity status từng bên và `operationally_feasible`. IaaS chưa đo capacity khiến giao điểm chỉ mang ý nghĩa tài chính. Không khuyến nghị cấu hình chỉ vì tại một volume nó rẻ hơn.

Sensitivity thay riêng N, CPU demand, memory, endpoint ratio, response bytes, concurrency, peak factor, active hours, min instances, price multiplier và labor rate. Với IaaS, memory/concurrency không tự đổi SKU VM; bảng ghi giới hạn này. Response size không ảnh hưởng egress khi `internet_egress_fraction=0`; labor rate không ảnh hưởng khi labor_hours=0. Cần thay input/nguồn thực để kết luận yếu tố nào quan trọng trong thực tế.

## Kiểm soát chi phí experiment

Runner reserve `request_bound × upper_usd/request + wall_bound_hours × upper_usd/hour` trước smoke test và run. Có max total requests và max RPS. Bound cần gồm phí chung và các bước idle/telemetry/cooldown; failed attempt vẫn giữ reservation. Chỉ thay ledger sau khi người vận hành đối soát, không tự hoàn lại dựa trên phỏng đoán.

GCP Budgets/alerts không phải hard spending cap. VM API và VM tạo tải có thể vẫn tính tiền khi runner dừng; tài nguyên khác, delayed metering hoặc bound nhập sai không do toolkit khống chế. Không có cam kết invoice tuyệt đối dưới budget; nghĩa của guard là không khởi chạy kế hoạch vượt bound người vận hành đã xác minh. Toolkit không tự tạo hay xóa cloud resources.
