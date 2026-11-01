from pathlib import Path

import nbformat as nbf


def main():
    notebook = nbf.v4.new_notebook()
    cells = []

    def md(text):
        cells.append(nbf.v4.new_markdown_cell(text))

    def code(text):
        cells.append(nbf.v4.new_code_cell(text))

    md("# So sánh thực nghiệm IaaS, PaaS và FaaS cho cùng API\n\n**Phúc Hoàng – Benchmark + Chi phí + Phân tích**\n\nNotebook tái lập pipeline từ raw data. Mặc định dùng **SIMULATED DATA – NOT REAL CLOUD MEASUREMENTS**. Không sử dụng dữ liệu mô phỏng làm bằng chứng thực nghiệm GCP.")
    md("## 1. Mục tiêu và câu hỏi nghiên cứu\n\nSo sánh latency, throughput, tỷ lệ lỗi, cold/warm, phản ứng scale-out và chi phí với cùng input, seed data và endpoint mix. Chênh lệch tài nguyên, concurrency và billing phải được ghi nhận riêng.")
    md("## 2. Thiết kế và mô tả dữ liệu\n\nĐơn vị thí nghiệm độc lập là một **run**. Request trong cùng run có thể tương quan. Raw k6 là JSONL Point; Monitoring giữ nguyên scalar/distribution, labels và intervals. Metadata chứa nguồn, config, seed và thời gian UTC. DEMO có 5 vòng; không xác nhận cloud đã được đo.")
    code("""import os, sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Markdown
ROOT = Path.cwd()
if not (ROOT / 'configs').exists(): ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from benchmark.config import load_config
from benchmark.parsers import load_dataset
from benchmark.statistics.analysis import analyze, bootstrap_ci
from benchmark.cost.model import CostModel
from benchmark.cost.report import cost_report
from benchmark.io import DEMO_LABEL, read_json
config = load_config()
MODE = os.environ.get('BENCH_MODE', 'DEMO').upper()
assert MODE in {'DEMO', 'REAL'}
DATA_ROOT = Path(os.environ.get('BENCH_DATA_ROOT', 'demo_data' if MODE == 'DEMO' else 'results'))
ANALYSIS = Path('results/processed') / MODE.lower()
FINANCIAL = Path('results/financial') / MODE.lower()
display(Markdown('**' + (DEMO_LABEL if MODE == 'DEMO' else 'REAL: kiểm tra validity từng run') + '**'))""")
    md("## 3. Đọc dữ liệu\n\nThay `BENCH_MODE=REAL` và `BENCH_DATA_ROOT` để đọc phép đo mới. Không tự tạo mẫu khi dữ liệu thật bị thiếu.")
    code("""requests, metadata, raw_metrics, quality = load_dataset(DATA_ROOT)
assert metadata, 'Chưa có metadata; chạy demo hoặc cung cấp raw dataset thật'
assert {m['data_mode'] for m in metadata.values()} == {MODE}, 'Không trộn các data modes'
display(requests.head())
display(pd.DataFrame([{'run_id': key, 'model': m['model'], 'scenario': m['scenario'], 'mode': m['data_mode']} for key, m in metadata.items()]).head())""")
    md("## 4. Kiểm tra tính hợp lệ\n\nKiểm tra timestamp UTC, missing fields, duplicate và schema. Bản sao làm sạch loại dòng không thể phân tích và duplicate chính xác; duplicate xung đột được cách ly. Raw luôn giữ nguyên.")
    code("""display(pd.DataFrame([{'run_id': k, 'valid_rows': v.get('valid_rows'), 'invalid_rows': v.get('invalid_rows'), 'duplicates': v.get('duplicates'), 'warmup_rows': v.get('warmup_rows')} for k,v in quality.items()]).head(12))
assert requests['latency_ms'].ge(0).all()
assert requests['timestamp'].dt.tz is not None""")
    md("## 5. Làm sạch dữ liệu\n\nDữ liệu warm-up không nằm trong steady measurement. Request lỗi và outlier hợp lệ được giữ. Unknown outcome không được mặc định là thành công. Phân loại first request cấp ứng dụng không đồng nghĩa confirmed cold.")
    code("""measured = requests.loc[requests['phase'].isin(['measurement', 'first_after_idle'])].copy()
display(measured.groupby(['model', 'classification']).size().unstack(fill_value=0))
display(measured.groupby('model')[['latency_ms','handler_ms','wall_ms']].count())""")
    md("## 6. Khám phá dữ liệu\n\nPhân phối latency có thể lệch phải. Không xóa đuôi phân phối để làm đẹp kết quả. Nhóm medium steady được dùng cho biểu đồ minh họa sau.")
    code("""cohort = measured.loc[(measured['scenario']=='steady') & (measured['load_level']=='medium')]
if len(cohort):
    fig, ax = plt.subplots(figsize=(8,4))
    for model, group in cohort.groupby('model'):
        x=np.sort(group['latency_ms']); ax.step(x, np.arange(1,len(x)+1)/len(x), label=model)
    ax.set(xscale='log', xlabel='Request latency (ms)', ylabel='ECDF', title=MODE+' • steady medium • kể cả lỗi')
    ax.legend(); plt.show()
else: print('Thiếu nhóm steady medium')""")
    md("## 7. Thống kê hiệu năng\n\nPercentile dùng nội suy tuyến tính NumPy. Standard deviation dùng `ddof=1`. Achieved throughput = completions trong cửa sổ / duration; cohort throughput bao gồm request measurement kết thúc trong grace period. Goodput và error rate được xuất riêng.")
    code("""tables = analyze(DATA_ROOT, ANALYSIS, resamples=config['experiments']['bootstrap_resamples'], minimum_samples=config['experiments']['minimum_samples'])
per_run=tables['per_run']; comparison=tables['comparison']
display(per_run.loc[per_run['endpoint']=='all', ['run_id','request_count','p50_ms','p95_ms','p99_ms','achieved_rps','error_rate_pct','valid_for_comparison']].head(12))""")
    md("## 8. Khoảng tin cậy bootstrap\n\nEstimand = trung bình thống kê theo run, không phải percentile của request gộp. Bootstrap 2.000 lần từ các run hợp lệ độc lập. Dưới 2 run: không có CI. Dưới 5 run: cảnh báo; p99 dưới 1.000 mẫu/run thiếu ổn định. CI là bất định lấy mẫu có điều kiện, không bao phủ mọi sai số cloud.")
    code("""display(comparison.loc[(comparison['metric']=='p95_ms') & (comparison['endpoint']=='all')].head(12))
display(pd.DataFrame([bootstrap_ci([10,20,30,40,50], seed=20261031)]))""")
    md("## 9. Steady-load\n\nĐọc low/medium/high riêng. Offered RPS là mục tiêu phát, achieved là số đo hoàn thành. Dropped iterations và generator saturation làm run không đủ giá trị so sánh chính thức.")
    code("""steady=per_run.loc[(per_run['scenario']=='steady') & (per_run['endpoint']=='all')]
display(steady.groupby(['model','load_level'])[['p95_ms','achieved_rps','offered_rps','error_rate_pct']].mean())
display(steady.loc[~steady['valid_for_comparison'], ['run_id','warning']])""")
    md("## 10. Burst-load\n\nDùng cửa sổ 10 giây, phân biệt baseline/burst/recovery. Với burst DEMO ngắn, một bin có thể cắt nhiều pha; khi đo thật cần chọn bin phù hợp.")
    code("""timeline=tables['timeline']
burst=timeline.loc[timeline['scenario']=='burst'] if len(timeline) else timeline
display(burst.head(12))
if len(burst): display(burst.groupby(['model','burst_phase'])[['p95_ms','p99_ms','achieved_rps','error_rate_pct']].mean())""")
    md("## 11. Cold / warm\n\nConfirmed cold yêu cầu bằng chứng nền tảng độc lập liên kết request. Process-first-request chỉ đo lần đầu tiến trình. Unknown giữ riêng. Idle 20 phút không bảo đảm scale-to-zero. Chênh lệch median cold/warm không phải phép đo chính xác overhead hạ tầng.")
    code("""display(tables['cold_warm'].head(12))
display(tables['cold_penalty'].head(12))""")
    md("## 12. Scale-out\n\nCloud Monitoring thường sampling 60 giây và trễ hiển thị. Thời gian scale-out được xác định bằng khoảng giữa sample cuối trước tăng và sample đầu quan sát tăng. IaaS một VM cố định: không áp dụng autoscaling; không biểu diễn 0 giây.")
    code("""display(tables['scaling'].head(15))
monitor=tables['monitoring']
if len(monitor): display(monitor.groupby(['model','metric'])['value'].agg(['count','mean']))""")
    md("## 13. Mô hình chi phí\n\nGiá Singapore có URL và bản chụp nguồn. CPU-seconds không được tính bằng N × p95. Estimator dùng mean service demand, CPU demand, overlap/concurrency, hourly traffic profile và startup assumptions; measurements billable-instance-time cần đúng kỳ/volume. Request-based khác instance-based. VM thanh toán full host e2-standard-2 dù container chỉ 1 vCPU/1 GiB. Firestore là chi phí chung nhưng retries cần khai báo theo mô hình.")
    code("""cost_input=Path(os.environ.get('BENCH_COST_WORKLOAD','configs/cost_workloads.yaml'))
cost_model=CostModel.from_files(Path('configs/pricing_catalog.yaml'),cost_input)
assert cost_model.workload['data_mode']==MODE, 'Đổi cost workload data_mode và assumptions cho phép đo REAL'
financial=cost_report(cost_model, FINANCIAL)
display(financial['cost_levels'][['model','level','monthly_requests','total_usd','compute_usd','shared_data_usd','capacity_status']])""")
    md("## 14. Điểm hòa vốn\n\nHàm chi phí có thể không giao nhau, có nhiều nghiệm hoặc trùng nhau trong khoảng. Tìm nghiệm kiểm tra residual để không tạo nghiệm giả ở bước nhảy. Log grid hữu hạn có thể bỏ sót tiếp xúc hẹp; bổ sung breakpoints khi dùng model bậc phức tạp. Nghiệm tài chính không chứng minh cả hai mô hình đáp ứng SLA/capacity.")
    code("""break_even=read_json(FINANCIAL/'break_even.json')
display(pd.DataFrame([{'left': x['left'],'right': x['right'],'status':x['status'],'roots':x['roots'],'coincident_intervals':x['coincident_intervals']} for x in break_even]))""")
    md("## 15. Sensitivity analysis\n\nThay từng giả định: CPU time, memory, mix, response size, concurrency, traffic peak, active hours, min instances, giá và công lao động. Giá trị baseline bằng 0 có thể làm sensitivity bằng 0; đó là điều kiện mô hình, không phải bằng chứng chi phí không tồn tại.")
    code("""sensitivity=financial['sensitivity']
display(sensitivity.assign(abs_delta=sensitivity['delta_usd'].abs()).sort_values('abs_delta',ascending=False).head(15))""")
    md("## 16. So sánh ba mô hình và SLA\n\nKhông gộp các workload khác nhau thành một xếp hạng duy nhất. Bảng performance và bảng cost có phạm vi khác nhau; cần hiệu chỉnh mean service/CPU/profile trước khi liên hệ chúng. INCONCLUSIVE là kết quả hợp lệ khi thiếu bằng chứng.")
    code("""from benchmark.decision_engine.report import case_studies
cases=case_studies(Path('reports/generated')/MODE.lower()/'decision')
display(pd.DataFrame([{'case':x['case'],'recommendation':x['result']['recommendation'],'status':x['result']['status']} for x in cases]))""")
    md("## 17. Sai số và threats to validity\n\nNetwork jitter; contention; caching; Firestore indexes/retries; khác biệt hardware và container limits; concurrency/workers/timeout; load generator bottleneck; quota; thời gian chạy ngắn; cold classification; sampling; giá thay đổi và workload không đại diện. Xem `reports/limitations.md` cho nguyên nhân, ảnh hưởng, giảm thiểu và giới hạn còn lại của từng yếu tố.")
    md("## 18. Nhận xét từ kết quả quan sát\n\nPhần dưới sinh số lượng run và trạng thái thực tế từ bảng; không viết sẵn nền tảng nhanh nhất/rẻ nhất.")
    code("""valid=per_run.loc[(per_run['endpoint']=='all') & per_run['valid_for_comparison']]
display(Markdown(f'Có **{len(metadata)} run**, trong đó **{len(valid)}** run có đủ điều kiện hiện tại.'))
if MODE=='DEMO':
    display(Markdown('**Không có kết luận thực nghiệm GCP từ notebook DEMO.** Các số liệu chỉ xác minh pipeline chạy được.'))
else:
    display(Markdown('Kết quả chỉ áp dụng các cấu hình/run hợp lệ. Cần kiểm tra CI, capacity, SLA và threats to validity trước khi kết luận.'))""")
    md("## 19. Tái lập và xuất kết quả\n\nChạy `python -m benchmark.cli export` sau analyze/cost để tạo PNG 300 DPI, SVG, HTML và báo cáo Markdown. Raw data bất biến. Lưu source Git SHA, dependency lock, source hashes, config, seed và experiment metadata cùng kết quả.")
    notebook.cells = cells
    notebook.metadata = {"kernelspec": {"display_name": "Python 3.12 (cloudbench)", "language": "python", "name": "python3"}, "language_info": {"name": "python", "version": "3.12"}}
    path = Path("notebooks/benchmark_analysis.ipynb")
    path.parent.mkdir(exist_ok=True)
    nbf.write(notebook, path)
    print(path)


if __name__ == "__main__":
    main()
