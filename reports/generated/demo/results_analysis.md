# Kết quả phân tích

**SIMULATED DATA – NOT REAL CLOUD MEASUREMENTS**

Dữ liệu DEMO chỉ kiểm thử pipeline; không là bằng chứng thực nghiệm GCP.

## Steady medium: các run độc lập

| model | run_id | request_count | p50_ms | p95_ms | p99_ms | achieved_rps | error_rate_pct | valid_for_comparison |
|---|---|---|---|---|---|---|---|---|
| faas | simulated-faas-steady-medium-mixed-r01 | 360 | 47.33 | 135.6 | 200.4 | 20 | 1.111 | True |
| faas | simulated-faas-steady-medium-mixed-r02 | 360 | 39.29 | 113.9 | 167.5 | 20 | 1.944 | True |
| faas | simulated-faas-steady-medium-mixed-r03 | 360 | 32.86 | 86.15 | 167.4 | 20 | 1.944 | True |
| faas | simulated-faas-steady-medium-mixed-r04 | 360 | 32.39 | 92.64 | 139.4 | 20 | 1.667 | True |
| faas | simulated-faas-steady-medium-mixed-r05 | 360 | 36.81 | 98.3 | 154.2 | 20 | 2.222 | True |
| iaas | simulated-iaas-steady-medium-mixed-r01 | 360 | 35.47 | 100.3 | 161.1 | 19.94 | 2.222 | True |
| iaas | simulated-iaas-steady-medium-mixed-r02 | 360 | 37.2 | 105.4 | 144 | 19.94 | 1.111 | True |
| iaas | simulated-iaas-steady-medium-mixed-r03 | 360 | 38.19 | 100.4 | 172.8 | 20 | 0.8333 | True |
| iaas | simulated-iaas-steady-medium-mixed-r04 | 360 | 37.19 | 100.2 | 167.9 | 19.94 | 1.667 | True |
| iaas | simulated-iaas-steady-medium-mixed-r05 | 360 | 36.93 | 118.5 | 220.9 | 20 | 1.111 | True |
| paas | simulated-paas-steady-medium-mixed-r01 | 360 | 37.17 | 114.9 | 317.5 | 20 | 0.2778 | True |
| paas | simulated-paas-steady-medium-mixed-r02 | 360 | 49.18 | 130.8 | 250 | 20 | 1.389 | True |
| paas | simulated-paas-steady-medium-mixed-r03 | 360 | 33.98 | 91.9 | 167.9 | 20 | 2.5 | True |
| paas | simulated-paas-steady-medium-mixed-r04 | 360 | 39.17 | 115 | 182.8 | 20 | 1.667 | True |
| paas | simulated-paas-steady-medium-mixed-r05 | 360 | 37.41 | 110.6 | 200.8 | 19.94 | 1.389 | True |

Có 15 run trong nhóm này; 15 run hợp lệ theo kiểm tra samples/dropped/status. Các request lỗi vẫn nằm trong phân phối latency.

## Khoảng tin cậy p95

| model | estimate | ci_lower | ci_upper | number_of_runs | sample_size | status |
|---|---|---|---|---|---|---|
| faas | 105.3 | 91.18 | 122.7 | 5 | 1800 | OK |
| iaas | 105 | 100.2 | 112.2 | 5 | 1800 | OK |
| paas | 112.6 | 101.1 | 123.5 | 5 | 1800 | OK |

Estimand là trung bình các p95 từng run. CI 95% dùng percentile bootstrap lấy lại các run độc lập; p99 với dưới 1.000 request/run được đánh dấu thiếu ổn định. Không dùng overlap CI như một kiểm định khác biệt có ý nghĩa.

## Chi phí theo các giả định được khai báo

| model | level | monthly_requests | total_usd | compute_usd | shared_data_usd | capacity_status |
|---|---|---|---|---|---|---|
| iaas | low | 100000 | 61.02 | 60.35 | 0.2326 | UNVERIFIED |
| paas | low | 100000 | 0.6444 | 0.3718 | 0.2326 | ESTIMATED_SUPPORTED |
| faas | low | 100000 | 0.6444 | 0.3718 | 0.2326 | ESTIMATED_SUPPORTED |
| iaas | medium | 2000000 | 61.93 | 60.35 | 1.144 | UNVERIFIED |
| paas | medium | 2000000 | 8.972 | 7.028 | 1.144 | ESTIMATED_SUPPORTED |
| faas | medium | 2000000 | 8.972 | 7.028 | 1.144 | ESTIMATED_SUPPORTED |
| iaas | high | 20000000 | 70.56 | 60.35 | 9.779 | UNVERIFIED |
| paas | high | 20000000 | 66.23 | 48.46 | 9.779 | ESTIMATED_SUPPORTED |
| faas | high | 20000000 | 66.23 | 48.46 | 9.779 | ESTIMATED_SUPPORTED |

Giá lấy từ catalog Singapore có nguồn; thời gian xử lý, traffic profile và concurrency là đầu vào giả định. Chưa đối soát hóa đơn. IaaS capacity UNVERIFIED nghĩa là chưa biết một VM đáp ứng peak; giao điểm chi phí không tự chứng minh tính khả thi.

## Điểm hòa vốn

- iaas / paas: ROOTS_FOUND; số nghiệm rời rạc 1; khoảng trùng [].

- iaas / faas: ROOTS_FOUND; số nghiệm rời rạc 1; khoảng trùng [].

- paas / faas: COINCIDENT_INTERVAL; số nghiệm rời rạc 0; khoảng trùng [[0.0, 1000000000.0]].

Tìm nghiệm trên log grid có kiểm tra residual. Hàm bậc có thể đổi bên mà không có điểm bằng nhau; trường hợp đó được ghi discontinuities. Không bảo đảm phát hiện mọi tiếp xúc hẹp chưa có breakpoint.

## Cold/warm và scale-out

Process-first-request chỉ là tín hiệu ở cấp ứng dụng. Confirmed cold cần log bằng chứng nền tảng liên kết request ID. Hiệu median cold/warm là liên hệ giữa phân phối, không cô lập thời gian khởi tạo hạ tầng. IaaS cố định có scale-out = NOT_APPLICABLE_FIXED_VM, không phải 0 giây.

Monitoring lấy mẫu 60 giây, có độ trễ hiển thị; scale-out được báo khoảng giữa hai sample. Burst ngắn hơn sampling có thể bị bỏ lỡ. Container startup, handler duration, k6 duration và client wall time là các phép đo khác nhau.

## Kết luận trong phạm vi dữ liệu

Chưa có benchmark GCP thật trong bộ dữ liệu DEMO. Không thể kết luận nền tảng nhanh nhất/rẻ nhất trong thực tế. Khi thay dữ liệu REAL, cần kiểm tra contract, tài nguyên thực, độc lập các run, capacity, SLA và sensitivity trước khi đề xuất.
