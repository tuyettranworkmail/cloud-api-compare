from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from benchmark.config import load_config
from benchmark.cost.model import CostModel

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config():
    return copy.deepcopy(load_config(ROOT / "configs"))


@pytest.fixture
def cost_model():
    catalog = yaml.safe_load((ROOT / "configs/pricing_catalog.yaml").read_text(encoding="utf-8"))
    workload = yaml.safe_load((ROOT / "configs/cost_workloads.yaml").read_text(encoding="utf-8"))
    return CostModel(catalog, workload)
