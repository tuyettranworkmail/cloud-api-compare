"""Lớp truy cập dữ liệu. MemoryStore để chạy local/test, FirestoreStore để chạy thật.

Quy ước hợp đồng dữ liệu (xem tài liệu kế hoạch, mục 3.3):
- Đọc từ collection  `items`        (100.000 bản ghi seed, KHÔNG ghi vào đây khi đo).
- Ghi vào collection `items_write`  (id ngẫu nhiên UUID4, hoặc = Idempotency-Key).
"""
from __future__ import annotations

import os
import uuid
from typing import Protocol

from .service import gen_item, item_id

READ_COLLECTION = "items"
WRITE_COLLECTION = "items_write"


class ItemStore(Protocol):
    def get(self, item_id: str) -> dict | None: ...
    def create(self, doc: dict, idempotency_key: str | None) -> tuple[str, bool, dict]: ...


class MemoryStore:
    def __init__(self, seed_count: int = 1000):
        self.items = {item_id(i): gen_item(i) for i in range(1, seed_count + 1)}
        self.written: dict[str, dict] = {}

    def get(self, item_id_: str) -> dict | None:
        return self.items.get(item_id_)

    def create(self, doc, idempotency_key):
        new_id = idempotency_key or uuid.uuid4().hex
        if new_id in self.written:
            return new_id, False, self.written[new_id]
        self.written[new_id] = doc
        return new_id, True, doc


class FirestoreStore:
    def __init__(self, project: str | None = None):
        from google.cloud import firestore  # import muộn: không cần khi chạy MemoryStore

        self.db = firestore.Client(project=project)

    def get(self, item_id_: str) -> dict | None:
        snap = self.db.collection(READ_COLLECTION).document(item_id_).get()
        return snap.to_dict() if snap.exists else None

    def create(self, doc, idempotency_key):
        from google.api_core.exceptions import AlreadyExists

        new_id = idempotency_key or uuid.uuid4().hex
        ref = self.db.collection(WRITE_COLLECTION).document(new_id)
        try:
            ref.create(doc)  # create() thất bại nếu document đã tồn tại -> nguyên tử
            return new_id, True, doc
        except AlreadyExists:
            return new_id, False, ref.get().to_dict()


def make_store() -> ItemStore:
    """Chọn store theo biến môi trường STORE=memory|firestore (mặc định memory)."""
    kind = os.getenv("STORE", "memory").lower()
    if kind == "firestore":
        return FirestoreStore(project=os.getenv("GCP_PROJECT") or None)
    return MemoryStore(seed_count=int(os.getenv("SEED_COUNT", "1000")))
