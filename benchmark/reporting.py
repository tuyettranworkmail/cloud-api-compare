from __future__ import annotations

import html
from pathlib import Path

import pandas as pd

from benchmark.decision_engine.report import case_studies
from benchmark.io import read_json
from benchmark.visualization.charts import read_table


def markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "Thiếu dữ liệu."
    columns = list(frame.columns)
    def cell(value):
        if pd.isna(value):
            return "N/A"
        return (f"{value:.4g}" if isinstance(value, float) else str(value)).replace("|", "/").replace("\n", " ")
    return "| " + " | ".join(columns) + " |\n|" + "|".join(["---"] * len(columns)) + "|\n" + "\n".join("| " + " | ".join(cell(v) for v in row) + " |" for row in frame.itertuples(index=False, name=None))


def build_research_report(analysis: Path, financial: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    provenance = read_json(analysis / "provenance.json")
    label = provenance["label"]
    runs = read_table(analysis, "per_run")
    comparison = read_table(analysis, "comparison")
    levels = read_table(financial, "cost_levels")
    parts = [f"# Kết quả phân tích\n\n**{label}**", "Dữ liệu DEMO chỉ kiểm thử pipeline; không là bằng chứng thực nghiệm GCP." if "DEMO" in provenance["data_modes"] else "Dữ liệu REAL; chỉ các run hợp lệ được dùng cho khoảng tin cậy. Thiếu metric được giữ là thiếu, không thay bằng 0."]
    if not runs.empty:
        summary = runs.loc[(runs["scenario"] == "steady") & (runs["load_level"] == "medium") & (runs["endpoint"] == "all")]
        parts += ["## Steady medium: các run độc lập", markdown_table(summary[["model", "run_id", "request_count", "p50_ms", "p95_ms", "p99_ms", "achieved_rps", "error_rate_pct", "valid_for_comparison"]])]
        parts += [f"Có {len(summary)} run trong nhóm này; {int(summary['valid_for_comparison'].sum())} run hợp lệ theo kiểm tra samples/dropped/status. Các request lỗi vẫn nằm trong phân phối latency."]
    if not comparison.empty:
        selected = comparison.loc[(comparison["scenario"] == "steady") & (comparison["load_level"] == "medium") & (comparison["endpoint"] == "all") & (comparison["metric"] == "p95_ms")]
        parts += ["## Khoảng tin cậy p95", markdown_table(selected[["model", "estimate", "ci_lower", "ci_upper", "number_of_runs", "sample_size", "status"]]), "Estimand là trung bình các p95 từng run. CI 95% dùng percentile bootstrap lấy lại các run độc lập; p99 với dưới 1.000 request/run được đánh dấu thiếu ổn định. Không dùng overlap CI như một kiểm định khác biệt có ý nghĩa."]
    if not levels.empty:
        parts += ["## Chi phí theo các giả định được khai báo", markdown_table(levels[["model", "level", "monthly_requests", "total_usd", "compute_usd", "shared_data_usd", "capacity_status"]]), "Giá lấy từ catalog Singapore có nguồn; thời gian xử lý, traffic profile và concurrency là đầu vào giả định. Chưa đối soát hóa đơn. IaaS capacity UNVERIFIED nghĩa là chưa biết một VM đáp ứng peak; giao điểm chi phí không tự chứng minh tính khả thi."]
    if (financial / "break_even.json").exists():
        intersections = read_json(financial / "break_even.json")
        parts += ["## Điểm hòa vốn"]
        for item in intersections:
            parts.append(f"- {item['left']} / {item['right']}: {item['status']}; số nghiệm rời rạc {len(item['roots'])}; khoảng trùng {item['coincident_intervals']}.")
        parts.append("Tìm nghiệm trên log grid có kiểm tra residual. Hàm bậc có thể đổi bên mà không có điểm bằng nhau; trường hợp đó được ghi discontinuities. Không bảo đảm phát hiện mọi tiếp xúc hẹp chưa có breakpoint.")
    parts += ["## Cold/warm và scale-out", "Process-first-request chỉ là tín hiệu ở cấp ứng dụng. Confirmed cold cần log bằng chứng nền tảng liên kết request ID. Hiệu median cold/warm là liên hệ giữa phân phối, không cô lập thời gian khởi tạo hạ tầng. IaaS cố định có scale-out = NOT_APPLICABLE_FIXED_VM, không phải 0 giây.", "Monitoring lấy mẫu 60 giây, có độ trễ hiển thị; scale-out được báo khoảng giữa hai sample. Burst ngắn hơn sampling có thể bị bỏ lỡ. Container startup, handler duration, k6 duration và client wall time là các phép đo khác nhau.", "## Kết luận trong phạm vi dữ liệu", "Chưa có benchmark GCP thật trong bộ dữ liệu DEMO. Không thể kết luận nền tảng nhanh nhất/rẻ nhất trong thực tế. Khi thay dữ liệu REAL, cần kiểm tra contract, tài nguyên thực, độc lập các run, capacity, SLA và sensitivity trước khi đề xuất."]
    content = "\n\n".join(parts) + "\n"
    (output / "results_analysis.md").write_text(content, encoding="utf-8")
    (output / "report.html").write_text("<!doctype html><html lang='vi'><meta charset='utf-8'><title>Benchmark research</title><style>body{font:15px system-ui;max-width:1100px;margin:40px auto;line-height:1.6;background:#f8fafc;color:#172554}pre{white-space:pre-wrap}h1{font-size:28px}.notice{padding:18px;background:#fef3c7;border-left:5px solid #d97706}</style><body><h1>Cloud Benchmark • Phúc Hoàng</h1><div class='notice'>" + html.escape(label) + "</div><pre>" + html.escape(content) + "</pre></body></html>", encoding="utf-8")
    tables_dir = output / "tables"
    tables_dir.mkdir(exist_ok=True)
    for directory in (analysis, financial):
        for path in directory.glob("*.csv"):
            if path.stem not in {"requests", "monitoring"}:
                (tables_dir / path.name).write_bytes(path.read_bytes())
    case_studies(output / "decision")
    from benchmark.visualization.excel import export_workbook
    modes = provenance["data_modes"]
    if len(modes) == 1 and modes[0] in {"DEMO", "REAL"}:
        export_workbook(analysis, financial, output / f"benchmark_results_{modes[0].lower()}.xlsx")
