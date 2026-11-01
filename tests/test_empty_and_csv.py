import csv


from benchmark.parsers.k6 import clean_requests, parse_k6
from benchmark.statistics.analysis import analyze


def test_empty_dataset_analysis_explicit_no_data(tmp_path):
    tables = analyze(tmp_path / "empty", tmp_path / "processed", resamples=100)
    assert tables["requests"].empty
    assert tables["per_run"].empty


def test_native_csv_extra_tags_urlencoded(tmp_path):
    path = tmp_path / "k6.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["metric_name", "timestamp", "metric_value", "status", "extra_tags"])
        writer.writeheader()
        writer.writerow({"metric_name": "request_sample_ms", "timestamp": "1760000000", "metric_value": "42", "status": "200", "extra_tags": "request_id=r1&phase=measurement&success=true&classification=confirmed_warm&endpoint=read"})
    frame, _, report = parse_k6(path, {"run_id": "r", "model": "paas", "scenario": "steady", "data_mode": "REAL"})
    frame, _ = clean_requests(frame)
    assert frame.iloc[0]["request_id"] == "r1"
    assert frame.iloc[0]["success"]
    assert frame.iloc[0]["latency_ms"] == 42
