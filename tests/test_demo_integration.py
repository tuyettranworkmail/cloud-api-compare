from pathlib import Path

import nbformat

from benchmark.demo import generate_demo
from benchmark.io import file_hash, read_json
from benchmark.statistics.analysis import analyze


def test_generated_demo_roundtrip_has_provenance_errors_and_missing(config, tmp_path):
    config["workloads"]["idle"]["warm_requests"] = 4
    result = generate_demo(config, tmp_path / "demo", seed=42, repeats=1)
    tables = analyze(tmp_path / "demo", tmp_path / "processed", resamples=100)
    assert result["runs"] == 15
    assert set(tables["requests"]["data_mode"]) == {"DEMO"}
    assert tables["requests"]["success"].eq(False).any()
    assert tables["requests"]["handler_ms"].isna().any()
    assert tables["requests"]["classification"].eq("confirmed_cold").any()
    assert read_json(tmp_path / "processed/provenance.json")["data_modes"] == ["DEMO"]


def test_demo_seed_reproducible(config, tmp_path):
    generate_demo(config, tmp_path / "a", seed=12, repeats=1)
    generate_demo(config, tmp_path / "b", seed=12, repeats=1)
    paths = list((tmp_path / "a/raw").rglob("k6.jsonl"))
    for path in paths:
        assert file_hash(path) == file_hash(tmp_path / "b/raw" / path.relative_to(tmp_path / "a/raw"))


def test_notebook_is_valid_and_has_no_error_outputs():
    notebook = nbformat.read("notebooks/benchmark_analysis.ipynb", as_version=4)
    nbformat.validate(notebook)
    assert len([c for c in notebook.cells if c.cell_type == "code"]) >= 15
    executed = Path("notebooks/benchmark_analysis.executed.ipynb")
    if executed.exists():
        result = nbformat.read(executed, as_version=4)
        assert all(output.output_type != "error" for cell in result.cells if cell.cell_type == "code" for output in cell.outputs)
