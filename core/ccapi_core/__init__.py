"""Thư viện lõi dùng chung cho cả ba mô hình (IaaS, PaaS, FaaS).

Không phụ thuộc framework web. Adapter của từng mô hình chỉ gọi các hàm ở đây.
"""
from .service import (
    CATEGORIES,
    DEFAULT_COMPUTE_ROUNDS,
    MAX_COMPUTE_ROUNDS,
    ItemService,
    compute,
    gen_item,
)
from .store import ItemStore, MemoryStore, make_store

__all__ = [
    "CATEGORIES",
    "DEFAULT_COMPUTE_ROUNDS",
    "MAX_COMPUTE_ROUNDS",
    "ItemService",
    "ItemStore",
    "MemoryStore",
    "compute",
    "gen_item",
    "make_store",
]
