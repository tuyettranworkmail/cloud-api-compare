# Threats to validity

| Yếu tố | Nguyên nhân và ảnh hưởng | Giảm thiểu | Giới hạn còn lại |
|---|---|---|---|
| Network jitter | RTT/TLS/proxy biến thiên gây lệch latency | Load VM cùng region, cùng connection/timeout; giữ breakdown k6 | Không loại được đường đi và scheduling jitter |
| Cloud contention | Shared hardware/noisy neighbors | 5–10+ run, shuffle order, ghi thời gian | Không kiểm soát host placement |
| Cache | Firestore/client cache/index nóng khác nhau | Warm-up thống nhất, seed cố định, báo config cache | Không chứng minh cache nội bộ dịch vụ bằng nhau |
| Firestore | Index, contention, retry, query plan ảnh hưởng wall time và cost | Cùng DB/IDs, namespace writes, chạy tuần tự, log retry | Shared DB có biến thiên và hoạt động ngoài experiment |
| Load generator | CPU/RAM/network/VU không đủ gây thiếu offered rate | Generator monitor + dropped check + pilot | CPU thấp không chứng minh network đủ; không có NIC saturation detector tuyệt đối |
| Hardware khác | VM 2 vCPU/8 GiB vs app 1 vCPU/1 GiB; khác CPU generations | Cgroups evidence, tách app/billed capacity | Giới hạn giống nhau không tương đương hardware/scheduler |
| Concurrency | Hàng đợi/overlap ảnh hưởng throughput/cost | Đọc cấu hình thật, thêm controlled comparison | Worker model/Python GIL và runtime overhead vẫn khác |
| Worker/timeout | Nhiều worker hoặc timeout khác làm đổi distribution | Bàn giao flags, snapshot timeout, khai báo workers | Toolkit không tự kiểm chứng mọi app process worker |
| Autoscaling | Reactive policy và cooldown không quan sát liên tục | Thu instance series/stages, report bounds | Sampling minute có thể bỏ lỡ short scale events |
| Cold classification | First process request không là platform cold | Tách application-first/warm/unknown; cần independent evidence | Phải tin nguồn log chuẩn hóa và liên kết đúng instance/request |
| Sampling | Monitoring 60s, visibility delay | Chờ/collect lại, giữ intervals/buckets | Không xác định event với millisecond precision |
| Small sample | Ít run hoặc ít cold/p99 observations | Run bootstrap, warning, tăng mẫu | CI không bao phủ bias hệ thống/cloud drift |
| Short duration | Run ngắn chưa thấy steady/scaling hoàn chỉnh | Pilot và đủ 180s+ measurement; recovery riêng | Các cấu hình workload dài cần đo thêm |
| Quota/throttling | Giới hạn API/DB/VU dẫn lỗi và tail | Preflight quota review, cap RPS, lưu statuses | Không tự xác minh mọi quota động cấp project/account |
| Price change | List price, discount, currency, SKU thay đổi | Source snapshot/date/hash, optional Catalog API | Chưa có account invoice reconciliation |
| Cost occupancy | Poisson/perfect packing/hour bins khác scheduler thật | Mean CPU/wall riêng, measured billable-time và sensitivity | Không mô phỏng mọi burst/subsecond/autoscaling CPU boost |
| Free tier | Shared account credit hoặc daily quota không giống giả định | Mặc định off, eligibility + remaining fraction + daily calculation | Mixed billing modes/other services cần phân bổ ngoài model đơn giản |
| Workload representativeness | Seed/CPU algorithm/traffic shape khác production | Endpoint riêng + mixed, nhiều load/profile, verify evidence scope | Không suy kết quả cho mọi API hoặc traffic |
| Observational comparison | Khác config thường đi cùng service model | Ghi config/evidence/remaining confounders | Không cô lập được causal effect loại dịch vụ chỉ từ benchmark |
| DEMO | Synthetic distribution được thiết kế để test code | Watermark, data_mode, source separation | Không có giá trị chứng minh model cloud nào nhanh/rẻ hơn |
| Local tests | Fixture in-memory, loopback, không Firestore/GCP | LOCAL_TEST label và thư mục riêng | Chỉ chứng minh tích hợp script/parser/API hoạt động |

Không có kết luận “tốt nhất mọi trường hợp”. Khi thiếu confirmed cold, metrics hoặc scope thích hợp, kết quả hợp lệ là INSUFFICIENT_DATA/INCONCLUSIVE.
