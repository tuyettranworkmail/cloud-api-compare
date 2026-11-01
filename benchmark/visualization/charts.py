from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import seaborn as sns

from benchmark.io import DEMO_LABEL, read_json, write_json

COLORS = {"iaas": "#2563a6", "paas": "#db7a25", "faas": "#16856b"}


def read_table(directory: Path, name: str) -> pd.DataFrame:
    try:
        return pd.read_csv(directory / f"{name}.csv")
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame()


def export_charts(analysis: Path, financial: Path, output: Path, sla_ms=500) -> list[dict]:
    tables = {name: read_table(analysis, name) for name in ("requests", "per_run", "comparison", "timeline", "cold_warm", "scaling", "monitoring")}
    tables.update({name: read_table(financial, name) for name in ("cost_levels", "cost_breakdown", "cost_curve", "sensitivity")})
    modes = set()
    for table in tables.values():
        if not table.empty and "data_mode" in table:
            modes.update(table["data_mode"].dropna().unique())
    if len(modes) > 1:
        raise ValueError("Xuất biểu đồ riêng cho từng data_mode; không trộn DEMO/REAL")
    mode = next(iter(modes), "UNKNOWN")
    label = "NO DATA — NOT EXECUTED" if mode == "UNKNOWN" else DEMO_LABEL if mode == "DEMO" else "LOCAL TEST — NOT REAL CLOUD MEASUREMENTS" if mode == "LOCAL_TEST" else "REAL DATA — inspect run validity and cost assumptions"
    sns.set_theme(style="whitegrid", font_scale=.95)
    manifest = []
    output.mkdir(parents=True, exist_ok=True)
    req, runs, comp = tables["requests"], tables["per_run"], tables["comparison"]
    if not req.empty:
        req = req.loc[req["phase"].isin(["measurement", "first_after_idle"])]
    steady = runs.loc[(runs["scenario"] == "steady") & (runs["endpoint"] == "all")] if not runs.empty else runs
    # One declared medium-load cohort prevents accidental pooling of endpoints/scenarios/levels.
    cohort = req.loc[(req["scenario"] == "steady") & (req["load_level"] == "medium")] if not req.empty else req

    def make(folder, name, title, source, draw):
        directory = output / folder
        directory.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(figsize=(9, 5.2))
        try:
            has_data = draw(ax)
            if has_data is False:
                ax.text(.5, .5, "Thiếu dữ liệu / không áp dụng", ha="center", va="center", transform=ax.transAxes)
        except (KeyError, ValueError, TypeError) as error:
            plt.close(fig)
            raise RuntimeError(f"Chart {name} failed: {error}") from error
        ax.set_title(title, loc="left", fontsize=13, fontweight="bold", pad=15)
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(handles, labels, frameon=False, fontsize=8)
        fig.text(.02, .025, label, fontsize=8, color="#b45309" if mode == "DEMO" else "#334155", fontweight="bold")
        fig.text(.02, .005, f"Nguồn: {source}", fontsize=7, color="#475569")
        fig.tight_layout(rect=(0, .07, 1, 1))
        for extension in ("png", "svg"):
            fig.savefig(directory / f"{name}.{extension}", dpi=300, bbox_inches="tight")
        plt.close(fig)
        manifest.append({"name": name, "folder": folder, "source": str(source), "data_mode": mode})

    def grouped_bars(ax, table, metric, x="model", hue=None, ylabel="Latency (ms)"):
        if table.empty:
            return False
        sns.barplot(data=table, x=x, y=metric, hue=hue or x, palette=COLORS if (hue or x) == "model" else "muted", errorbar=None, ax=ax, legend=bool(hue))
        ax.set_ylabel(ylabel)
        ax.set_xlabel("Mô hình" if x == "model" else x)

    def line(ax, table, x, y, xlabel, ylabel):
        if table.empty:
            return False
        sns.lineplot(data=table, x=x, y=y, hue="model", palette=COLORS, estimator="mean", errorbar=None, ax=ax)
        ax.set(xlabel=xlabel, ylabel=ylabel)

    def quantiles(ax):
        data = steady.loc[steady["load_level"] == "medium"] if not steady.empty else steady
        if data.empty:
            return False
        wide = data.groupby("model")[["p50_ms", "p95_ms", "p99_ms"]].mean().reset_index().melt(id_vars="model", var_name="percentile", value_name="ms")
        grouped_bars(ax, wide, "ms", hue="percentile")
    make("performance", "01_latency_quantiles", "Trung bình percentile từng run • Steady medium", analysis / "per_run.csv", quantiles)
    for name, metric, title, ylabel in [("02_latency_vs_offered", "p95_ms", "p95 theo offered RPS", "p95 (ms)"), ("03_throughput_vs_offered", "achieved_rps", "Throughput đạt được theo tải yêu cầu", "Achieved throughput (request/s)"), ("04_error_vs_load", "error_rate_pct", "Tỷ lệ lỗi theo tải", "Error rate (%)")]:
        make("performance", name, title, analysis / "per_run.csv", lambda ax, metric=metric, ylabel=ylabel: line(ax, steady, "offered_rps", metric, "Offered rate (request/s)", ylabel))
    ep = runs.loc[(runs["scenario"] == "steady") & (runs["load_level"] == "medium") & (runs["endpoint"] != "all")] if not runs.empty else runs
    make("performance", "05_endpoint_comparison", "GET / POST / CPU • Steady medium", analysis / "endpoint_summary.csv", lambda ax: grouped_bars(ax, ep, "p95_ms", "endpoint", "model", "Mean run p95 (ms)"))

    def ecdf(ax):
        if cohort.empty:
            return False
        sns.ecdfplot(data=cohort, x="latency_ms", hue="model", palette=COLORS, ax=ax)
        ax.set(xlabel="Request latency (ms)", ylabel="ECDF", xscale="log")
    make("performance", "06_latency_ecdf", "Phân phối latency • Steady medium • kể cả lỗi", analysis / "requests.csv", ecdf)

    def box(ax):
        if cohort.empty:
            return False
        sns.boxplot(data=cohort, x="model", y="latency_ms", hue="model", palette=COLORS, showfliers=True, ax=ax, legend=False)
        ax.set(ylabel="Request latency (ms)", xlabel="Mô hình", yscale="log")
    make("performance", "07_latency_boxplot", "Boxplot • Steady medium • outliers được giữ", analysis / "requests.csv", box)

    def confidence(ax):
        if comp.empty:
            return False
        data = comp.loc[(comp["scenario"] == "steady") & (comp["load_level"] == "medium") & (comp["endpoint"] == "all") & (comp["metric"] == "p95_ms")].dropna(subset=["ci_lower", "ci_upper"])
        if data.empty:
            return False
        for i, row in enumerate(data.itertuples()):
            ax.errorbar(i, row.estimate, yerr=[[max(0, row.estimate - row.ci_lower)], [max(0, row.ci_upper - row.estimate)]], fmt="o", capsize=6, color=COLORS[row.model], label=f"{row.model}: n={row.number_of_runs} runs")
        ax.set_xticks(range(len(data)), data["model"])
        ax.set_ylabel("Mean run p95 ± 95% bootstrap CI (ms)")
    make("performance", "08_confidence_intervals", "Khoảng tin cậy từ các run độc lập", analysis / "comparison.csv", confidence)
    timeline = tables["timeline"]
    burst = timeline.loc[timeline["scenario"] == "burst"] if not timeline.empty else timeline
    for name, metric, title, ylabel in [("09_burst_request_rate", "achieved_rps", "Burst: throughput quan sát theo thời gian", "Achieved throughput (request/s)"), ("11_burst_p95", "p95_ms", "Burst: trung bình p95 trong từng cửa sổ 10 giây", "Mean bin p95 (ms)")]:
        make("scaling", name, title, analysis / "timeline.csv", lambda ax, metric=metric, ylabel=ylabel: line(ax, burst, "relative_seconds", metric, "Thời gian từ measurement start (s)", ylabel))

    def instances(ax):
        monitor = tables["monitoring"]
        if monitor.empty:
            return False
        data = monitor.loc[monitor["metric"] == "instance_count"].copy()
        if data.empty:
            return False
        data["seconds"] = pd.to_datetime(data["timestamp"], utc=True).groupby(data["run_id"]).transform(lambda s: (s - s.min()).dt.total_seconds())
        line(ax, data, "seconds", "value", "Từ sample đầu run (s)", "Instance count (active + idle)")
        ax.text(.02, .95, "Sampling 60s; IaaS cố định: N/A", transform=ax.transAxes, fontsize=8)
    make("scaling", "10_instance_count", "Số instance theo samples Monitoring", analysis / "monitoring.csv", instances)
    cw = tables["cold_warm"]
    make("scaling", "12_cold_warm", "Latency theo mức bằng chứng cold/warm", analysis / "cold_warm.csv", lambda ax: grouped_bars(ax, cw.loc[cw["scenario"] == "idle"] if not cw.empty else cw, "p50_ms", "classification", "model", "Mean run median (ms)"))

    def scale(ax):
        data = tables["scaling"]
        if data.empty:
            return False
        data = data.loc[data["status"] == "OBSERVED_INTERVAL"]
        if data.empty:
            return False
        for i, (model, part) in enumerate(data.groupby("model")):
            low, high = part["scale_out_lower_seconds"].mean(), part["scale_out_upper_seconds"].mean()
            ax.errorbar(i, (low + high) / 2, yerr=(high - low) / 2, fmt="o", capsize=8, color=COLORS[model], label=model)
        ax.set_ylabel("Khoảng quan sát scale-out (s); IaaS = N/A")
        ax.set_xticks([])
    make("scaling", "13_scale_out_intervals", "Scale-out: khoảng bất định do sampling", analysis / "scaling.csv", scale)
    idle = req.loc[req["phase"] == "first_after_idle"] if not req.empty else req
    make("scaling", "14_after_idle", "Request đầu sau idle • chưa mặc định là cold", analysis / "requests.csv", lambda ax: grouped_bars(ax, idle, "latency_ms"))
    levels, costs, curve = tables["cost_levels"], tables["cost_breakdown"], tables["cost_curve"]

    def breakdown(ax):
        if costs.empty:
            return False
        data = costs.loc[costs["level"] == "medium"].pivot_table(index="model", columns="component", values="usd", aggfunc="sum")
        data.loc[:, data.sum() > 0].plot.bar(stacked=True, ax=ax, colormap="tab20")
        ax.set_ylabel("USD / tháng (ước tính)")
    make("cost", "15_cost_breakdown", "Cấu phần chi phí • Medium", financial / "cost_breakdown.csv", breakdown)
    make("cost", "16_cost_levels", "Chi phí Low / Medium / High • ước tính", financial / "cost_levels.csv", lambda ax: grouped_bars(ax, levels, "total_usd", "level", "model", "USD / tháng"))

    def cost_curve(ax, roots=False):
        if curve.empty:
            return False
        line(ax, curve, "monthly_requests", "total_usd", "Request / tháng (log scale)", "USD / tháng (ước tính)")
        ax.set_xscale("log")
        if roots and (financial / "break_even.json").exists():
            for item in read_json(financial / "break_even.json"):
                for root in item["root_details"]:
                    ax.scatter(root["requests"], root["cost_usd"], color="black", marker="x", zorder=5)
        ax.text(.02, .96, "Capacity/SLA phải được xác minh riêng", transform=ax.transAxes, va="top", fontsize=8)
    make("cost", "17_cost_vs_requests", "Chi phí theo lưu lượng và giả định phân bố tải", financial / "cost_curve.csv", cost_curve)
    make("cost", "18_break_even", "Giao điểm tài chính • không ép tồn tại nghiệm", financial / "break_even.json", lambda ax: cost_curve(ax, roots=True))

    def unit_cost(ax):
        if curve.empty:
            return False
        line(ax, curve, "monthly_requests", "cost_per_million_usd", "Request / tháng", "USD / một triệu request")
        ax.set(xscale="log", yscale="log")
    make("cost", "19_cost_per_million", "Chi phí chuẩn hóa theo một triệu request", financial / "cost_curve.csv", unit_cost)

    def tornado(ax):
        data = tables["sensitivity"]
        if data.empty:
            return False
        data = data.loc[data["model"] == "paas"]
        pivot = data.pivot(index="parameter", columns="direction", values="delta_usd")
        order = pivot.abs().max(axis=1).sort_values().index
        pivot.loc[order].plot.barh(ax=ax, color=["#db7a25", "#2563a6"])
        ax.set_xlabel("Thay đổi USD / tháng so với baseline PaaS")
    make("cost", "20_sensitivity_tornado", "Độ nhạy chi phí • các giả định thay đổi riêng", financial / "sensitivity.csv", tornado)

    def tradeoff(ax):
        if levels.empty or steady.empty:
            return False
        performance = steady.loc[steady["load_level"] == "medium"].groupby("model", as_index=False)[["p95_ms", "achieved_rps", "error_rate_pct"]].mean()
        merged = performance.merge(levels.loc[levels["level"] == "medium"], on="model")
        for row in merged.itertuples():
            ax.scatter(row.total_usd, row.p95_ms, s=100, color=COLORS[row.model], label=row.model)
            ax.annotate(row.model, (row.total_usd, row.p95_ms), xytext=(7, 6), textcoords="offset points")
        ax.set(xlabel="USD / tháng (Medium giả định)", ylabel="Mean run p95 (ms) • steady medium")
    make("performance", "21_performance_cost_tradeoff", "Hiệu năng – chi phí • hai phạm vi cần hiệu chỉnh", f"{analysis}/per_run.csv + {financial}/cost_levels.csv", tradeoff)
    make("performance", "22_latency_cost_scatter", "Latency và chi phí • không suy ra SLA từ giá", f"{analysis}/per_run.csv + {financial}/cost_levels.csv", tradeoff)

    def sla(ax):
        if steady.empty:
            return False
        data = steady.loc[steady["load_level"] == "medium"]
        grouped_bars(ax, data, "p95_ms", ylabel="Mean run p95 (ms)")
        ax.axhline(sla_ms, color="#b91c1c", linestyle="--", label=f"SLA minh họa {sla_ms:g} ms")
    make("performance", "23_sla_comparison", "SLA tham số • đánh giá trong phạm vi đã đo", analysis / "per_run.csv", sla)

    def decision(ax):
        ax.axis("off")
        boxes = [("Workload + control + SLA + budget", .5, .92), ("Bằng chứng đại diện?", .5, .74), ("Chưa đủ → INCONCLUSIVE", .18, .53), ("Lọc capability / cold / capacity", .70, .53), ("Chi phí + sensitivity + vận hành", .70, .30), ("Đề xuất có điều kiện / INCONCLUSIVE", .70, .08)]
        for text, x, y in boxes:
            ax.text(x, y, text, transform=ax.transAxes, ha="center", va="center", fontsize=9, bbox={"boxstyle": "round,pad=.6", "fc": "#eff6ff", "ec": "#2563a6"})
        for start, end in [((.5, .87), (.5, .79)), ((.45, .69), (.18, .58)), ((.55, .69), (.70, .58)), ((.70, .48), (.70, .35)), ((.70, .25), (.70, .13))]:
            ax.annotate("", xy=end, xytext=start, xycoords="axes fraction", arrowprops={"arrowstyle": "->", "color": "#475569"})
    make("decision_tree", "24_decision_tree", "Cây quyết định dựa trên bằng chứng", "benchmark/decision_engine/engine.py; decision_tree.mmd", decision)
    if not runs.empty:
        interactive = px.scatter(runs, x="offered_rps", y="p95_ms", color="model", symbol="scenario", hover_data=["run_id", "endpoint", "request_count", "valid_for_comparison"], color_discrete_map=COLORS, title=label, labels={"offered_rps": "Offered request/s", "p95_ms": "Per-run p95 (ms)"})
        interactive.write_html(output / "interactive_benchmark.html", include_plotlyjs=True)
    write_json(output / "chart_manifest.json", manifest)
    return manifest
