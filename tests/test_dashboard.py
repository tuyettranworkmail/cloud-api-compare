from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "dashboard/app.py"


def test_dashboard_overview_smoke():
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    assert app.title[0].value == "Overview"


def test_dashboard_real_missing_is_explicit():
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.sidebar.radio[0].set_value("REAL").run()
    assert not app.exception
    assert any("Chưa có dữ liệu" in info.value for info in app.info)


@pytest.mark.parametrize("page", ["Benchmark Results", "Performance Comparison", "Cold Start & Autoscaling", "Cost Analysis", "Break-even Simulator", "Decision Tree", "Experiment Metadata"])
def test_all_dashboard_pages_have_no_runtime_errors(page):
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.sidebar.radio[1].set_value(page).run()
    assert not app.exception
