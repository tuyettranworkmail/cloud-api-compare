# Tái lập

1. Dùng Python 3.12, `requirements-lock.txt`, k6 v2.3.0; ghi thêm OS và host hardware. Dependency resolution trên OS khác cần chạy lại tests/smoke.
2. Lưu Git SHA; nếu thư mục chưa là Git repo, runner ghi `git_sha: null` và hash các file Python/JS/YAML. Bản source trong bàn giao là nguồn tái lập; nên commit trước khi đo thật.
3. Giữ nguyên config/version/seed/endpoint input/dataset ID/comparison mode. Không commit `.env`, tokens hay ADC keys.
4. DEMO: `python -m benchmark.cli demo --all` sinh 75 run từ seed 20261031. `python scripts/execute_notebook.py` xác minh notebook. Script không liên hệ GCP.
5. REAL: cùng raw run directory có metadata và k6.jsonl/CSV; native Monitoring/logs optional giữ cạnh run. `analyze` chọn attempt số lớn nhất mỗi canonical run; attempt latest failed không bị thay bằng một attempt cũ thành công để làm đẹp dữ liệu.
6. Mọi timestamp raw/processed UTC; lịch trình/ngày bàn giao dùng Asia/Saigon. Không normalize UTC bằng cách gắn timezone cho thời gian local không rõ nguồn.
7. JSON outputs dùng null cho không xác định; CSV dùng ô trống/NaN. N/A khác 0. Raw giữ các distribution và errors; processed quarantine có quality report.
8. Sau đổi dữ liệu, chạy analyze → cost (cùng mode và assumptions mới) → export → notebook. Không tái dùng hình cũ với caption run mới.
9. Kiểm tra data_modes trong provenance và footer hình. LOCAL_TEST chỉ kiểm thử k6 thật trên fixture; nó không là REAL GCP và không được chuyển nhãn.
10. Lưu mã nguồn, raw, metadata, source price archives, lockfile, reports và chart manifest cùng phiên bản. SHA256 file metadata ghi các artifact ngay sau run.

Các lệnh kiểm tra và trạng thái thực thi có trong `reports/verification.json` sau bước verification bàn giao. Nếu collector không chạy được vì thiếu ADC, giữ trạng thái NOT_EXECUTED/NO_DATA/ERROR có nguyên nhân; không tạo raw GCP giả để đạt checklist.
