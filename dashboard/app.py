"""Streamlit presentation UI reading repository outputs; no invented KPI values."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.cost.model import CostModel  # noqa: E402
from benchmark.io import DEMO_LABEL, read_json  # noqa: E402
from benchmark.visualization.charts import COLORS, read_table  # noqa: E402

st.set_page_config(page_title="CloudBench • Phúc Hoàng", page_icon="☁", layout="wide")
st.markdown("""<style>
.stApp{background:#f5f7fb}h1,h2,h3{color:#142b4a}div[data-testid="stMetric"]{background:white;padding:20px;border-radius:12px;border:1px solid #e3eaf3;box-shadow:0 3px 8px #163b6510}
[data-testid="stSidebar"]{background:#10243d}[data-testid="stSidebar"] *{color:#e6eef8}[data-testid="stSidebar"] input{color:#132d4c}
.eyebrow{color:#467398;letter-spacing:2px;font-weight:700;font-size:12px}.sub{color:#64748b;font-size:15px}
</style>""", unsafe_allow_html=True)
with st.sidebar:
    st.markdown("## ☁ CloudBench")
    st.caption("RESEARCH WORKSPACE • PHÚC HOÀNG")
    mode = st.radio("Data mode", ["DEMO", "REAL"])
    page = st.radio("Trang", ["Overview", "Benchmark Results", "Performance Comparison", "Cold Start & Autoscaling", "Cost Analysis", "Break-even Simulator", "Decision Tree", "Experiment Metadata"])
    st.divider()
    st.caption("GCP • asia-southeast1\nPython / k6 / Cloud Monitoring")

analysis = ROOT / "results" / "processed" / mode.lower()
financial = ROOT / "results" / "financial" / mode.lower()
if mode == "DEMO":
    st.warning(DEMO_LABEL)
else:
    st.info("REAL: chỉ hiển thị dữ liệu đã thu thập. Không sinh số đo để lấp phần thiếu.")
st.markdown('<div class="eyebrow">CLOUD PERFORMANCE & FINOPS</div>', unsafe_allow_html=True)
st.title(page)
st.markdown('<div class="sub">So sánh cùng API trên IaaS · PaaS · FaaS với dữ liệu có thể kiểm chứng.</div>', unsafe_allow_html=True)
st.write("")
if not (analysis / "provenance.json").exists():
    st.info("Chưa có dữ liệu cho chế độ này. Chạy analyze với dữ liệu tương ứng; xem README.")
    st.stop()
provenance = read_json(analysis / "provenance.json")
if provenance["data_modes"] != [mode]:
    st.error("Provenance không khớp data mode đã chọn; dừng hiển thị để tránh nhầm nguồn.")
    st.stop()
tables = {name: read_table(analysis, name) for name in ("per_run", "comparison", "requests", "cold_warm", "scaling", "timeline", "monitoring")}
with st.sidebar:
    filtered = tables["per_run"].copy()
    selectors = [("Model", "model"), ("Scenario", "scenario"), ("Endpoint", "endpoint"), ("Load level", "load_level"), ("Run", "run_id")]
    selections = {}
    for title, column in selectors:
        values = sorted(filtered[column].dropna().unique()) if not filtered.empty else []
        default = ["all"] if column == "endpoint" and "all" in values else values
        selections[column] = st.multiselect(title, values, default=default)
        filtered = filtered.loc[filtered[column].isin(selections[column])] if column in filtered else filtered
runs = filtered
if not runs.empty:
    unique_runs = runs.drop_duplicates("run_id")
    kpis = st.columns(6)
    for col, metric, title, unit in zip(kpis, ["p50_ms", "p95_ms", "p99_ms", "achieved_rps", "error_rate_pct", "cold_ratio_pct"], ["P50 / run", "P95 / run", "P99 / run", "Throughput / run", "Error rate / run", "Confirmed cold / run"], ["ms", "ms", "ms", "req/s", "%", "%"]):
        value = unique_runs[metric].mean()
        col.metric(title, f"{value:,.2f} {unit}" if pd.notna(value) else "N/A")
    st.caption("KPI = trung bình mô tả từng run trong bộ lọc; khi chọn nhiều workload, dùng bảng CI theo nhóm để kết luận.")
else:
    st.info("Không có run phù hợp bộ lọc.")


def scatter(data, x, y, title):
    if data.empty:
        st.info("Thiếu dữ liệu.")
        return
    st.plotly_chart(px.scatter(data, x=x, y=y, color="model", color_discrete_map=COLORS, hover_data=[c for c in ["run_id", "endpoint", "scenario", "load_level"] if c in data], title=title), width="stretch")


if page == "Overview":
    a, b = st.columns([2, 1])
    with a:
        scatter(runs, "offered_rps", "p95_ms", "Latency theo tải • mỗi điểm là một run")
    with b:
        st.subheader("Chất lượng bằng chứng")
        st.metric("Run trong dataset", provenance["runs"])
        st.metric("Run được chọn", runs["run_id"].nunique())
        st.write("Khuyến nghị: **INCONCLUSIVE** khi chưa có bằng chứng REAL phù hợp workload.")
        st.caption("Cold flag cấp process không xác nhận toàn bộ thời gian khởi tạo hạ tầng.")
elif page == "Benchmark Results":
    st.dataframe(runs, hide_index=True, width="stretch")
    st.download_button("Tải CSV của bộ lọc", runs.to_csv(index=False).encode("utf-8-sig"), "benchmark_filtered.csv", "text/csv")
elif page == "Performance Comparison":
    scatter(runs, "offered_rps", "achieved_rps", "Offered rate và achieved throughput (request/s)")
    comp = tables["comparison"]
    for column in ("model", "scenario", "endpoint", "load_level"):
        if column in comp:
            comp = comp.loc[comp[column].isin(selections[column])]
    st.dataframe(comp, hide_index=True, width="stretch")
elif page == "Cold Start & Autoscaling":
    cold = tables["cold_warm"]
    cold = cold.loc[cold["run_id"].isin(runs["run_id"])] if not cold.empty else cold
    if not cold.empty:
        st.plotly_chart(px.box(cold, x="classification", y="p50_ms", color="model", color_discrete_map=COLORS, title="Các median từng run theo bằng chứng cold/warm"), width="stretch")
    scale = tables["scaling"]
    st.dataframe(scale.loc[scale["run_id"].isin(runs["run_id"])] if not scale.empty else scale, hide_index=True, width="stretch")
    st.caption("Scale-out: sampling 60 giây; IaaS một VM có trạng thái NOT_APPLICABLE, không phải 0 giây.")
elif page == "Cost Analysis":
    data = read_table(financial, "cost_levels")
    if not data.empty and set(data["data_mode"]) != {mode}:
        st.error("Nguồn chi phí không khớp mode")
        st.stop()
    if not data.empty:
        st.plotly_chart(px.bar(data, x="level", y="total_usd", color="model", barmode="group", color_discrete_map=COLORS, title="Ước tính chi phí USD / tháng"), width="stretch")
        st.dataframe(data[["model", "level", "total_usd", "compute_usd", "shared_data_usd", "capacity_status"]], hide_index=True)
    else:
        st.info("Chưa có cost outputs cho mode này.")
elif page == "Break-even Simulator":
    st.caption("Mô phỏng chi phí theo giá catalog; thay đổi giả định không tạo ra số đo cloud.")
    n = st.number_input("Request / tháng", 0, 1_000_000_000, 2_000_000, step=100_000)
    concurrency = st.slider("Concurrency giả định", 1, 80, 10)
    profile = st.selectbox("Phân bố tải", ["uniform", "business", "bursty"])
    simulator = CostModel.from_files(ROOT / "configs/pricing_catalog.yaml", ROOT / "configs/cost_workloads.yaml")
    simulator.workload["assumptions"]["distribution"] = profile
    for m in ("paas", "faas"):
        simulator.workload["models"][m]["concurrency"] = concurrency
    st.dataframe(pd.DataFrame([{k: v for k, v in simulator.estimate(m, n).items() if k in {"model", "total_usd", "capacity_status", "method"}} for m in ("iaas", "paas", "faas")]), hide_index=True)
    curve = read_table(financial, "cost_curve")
    if not curve.empty:
        st.plotly_chart(px.line(curve, x="monthly_requests", y="total_usd", color="model", log_x=True, color_discrete_map=COLORS, title="Đường baseline đã xuất • không phản ánh slider phía trên"), width="stretch")
elif page == "Decision Tree":
    image = ROOT / "charts" / mode.lower() / "decision_tree" / "24_decision_tree.png"
    if image.exists():
        st.image(str(image))
    cases = ROOT / "reports/generated/demo/decision/case_studies.json"
    if mode == "DEMO" and cases.exists():
        for case in read_json(cases):
            with st.expander(case["case"]):
                st.json(case["result"])
    st.caption("Dùng benchmark.decision_engine.recommend cho đầu vào workload và evidence thực. Không quyết định chỉ từ request/tháng.")
elif page == "Experiment Metadata":
    st.json(provenance)
    st.json(read_json(analysis / "quality.json"))
    st.caption("Nguồn metadata gốc nằm cạnh từng raw k6.jsonl; token không xuất trong metadata.")
