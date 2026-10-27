"""Logic nghiệp vụ: đọc, ghi, tác vụ CPU. Đây là "hợp đồng" hành vi của API."""
from __future__ import annotations

import hashlib
import random
from datetime import datetime, timezone

CATEGORIES = [f"cat-{i:02d}" for i in range(10)]

# Số vòng băm mặc định. Chạy scripts/calibrate_compute.py trên VM 1 vCPU
# để chỉnh sao cho mất khoảng 50-100 ms, rồi ĐÓNG BĂNG giá trị này.
DEFAULT_COMPUTE_ROUNDS = 200_000
MAX_COMPUTE_ROUNDS = 2_000_000

SEED = 42
N_ITEMS = 100_000


def item_id(i: int) -> str:
    """i từ 1 đến 100000 -> item-000001 ... item-100000"""
    return f"item-{i:06d}"


def gen_item(i: int, seed: int = SEED) -> dict:
    """Sinh bản ghi thứ i một cách xác định (cùng seed -> cùng dữ liệu)."""
    rng = random.Random(f"{seed}-{i}")
    base = hashlib.sha256(f"{seed}-{i}".encode()).hexdigest()  # 64 ký tự
    return {
        "name": f"Item {i}",
        "category": CATEGORIES[rng.randrange(len(CATEGORIES))],
        "value": rng.randint(0, 1_000_000),
        "payload": (base * 8)[:512],  # đúng 512 ký tự
        "created_at": "2026-01-01T00:00:00Z",
    }


def compute(n: int = DEFAULT_COMPUTE_ROUNDS) -> dict:
    """Tác vụ CPU: chuỗi băm SHA-256 lặp n vòng (xác định, không I/O)."""
    if n < 1 or n > MAX_COMPUTE_ROUNDS:
        raise ValueError(f"n phải trong khoảng 1..{MAX_COMPUTE_ROUNDS}")
    d = b"ccapi"
    for _ in range(n):
        d = hashlib.sha256(d).digest()
    return {"digest": d.hex(), "rounds": n}


class ItemService:
    def __init__(self, store):
        self.store = store

    def get_item(self, item_id_: str) -> dict | None:
        doc = self.store.get(item_id_)
        if doc is None:
            return None
        return {"id": item_id_, **doc}

    def create_item(self, data: dict, idempotency_key: str | None = None) -> tuple[dict, bool]:
        """Trả về (bản ghi, created). created=False nếu trùng Idempotency-Key."""
        doc = {
            "name": data["name"],
            "category": data["category"],
            "value": data["value"],
            "payload": data["payload"],
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        new_id, created, stored = self.store.create(doc, idempotency_key)
        return {"id": new_id, **stored}, created
