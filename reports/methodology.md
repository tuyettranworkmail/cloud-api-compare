# Phương pháp nghiên cứu

Thiết kế blocked repeated experiment: cùng seed data/CPU input/endpoint mix, cùng region, load generator riêng, ba deployment chạy tuần tự và shuffle thứ tự trong mỗi vòng. Mặc định 5 independent runs mỗi cấu hình; measurement steady tách warm-up, burst có giai đoạn baseline/ramp/hold/recovery, idle điều phối bằng tiến trình riêng.

Kiểm tra contract trước đo là điều kiện bắt buộc: OpenAPI operation/schema, methods, fixed input, normalized payload và determinism CPU. Controlled comparison cần bằng chứng app limits và concurrency; deployment comparison ghi config differences và không quy mọi khác biệt về loại dịch vụ.

Đơn vị độc lập cho suy luận là run. Thống kê request kể cả lỗi, giữ outlier, percentile nội suy tuyến tính, standard deviation mẫu. CI 95% percentile bootstrap trên các metric từng run, B=2.000. Missing và invalid được báo riêng. Cold classification dùng mức bằng chứng; không suy cold time từ client−handler. Scaling interval được báo theo sampling, không giả độ chính xác mili giây.

FinOps tính riêng host capacity và container limits; mean/CPU demand/traffic occupancy có giả định công khai. Full costs có và không có Firestore dùng chung. Free tier được quản theo eligibility/phạm vi tài khoản. Break-even có thể không tồn tại hoặc trùng interval. Quyết định chỉ khi evidence phù hợp SLA/control/capacity/budget/operations, nếu thiếu trả INCONCLUSIVE.

Chi tiết thực thi: [protocol](../docs/benchmark_protocol.md), [metric definitions](../docs/metric_definitions.md), [cost model](../docs/cost_assumptions.md). **Các output demo không là bằng chứng GCP.**
