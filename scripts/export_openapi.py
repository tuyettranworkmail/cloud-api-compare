"""Xuất contracts/openapi.yaml từ app FastAPI. Chạy lại mỗi khi đổi hợp đồng."""
import os
import sys

root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(root, "core"))
sys.path.insert(0, os.path.join(root, "adapters", "fastapi"))
os.environ.setdefault("STORE", "memory")

import yaml  # noqa: E402

from app import app  # noqa: E402

out = os.path.join(root, "contracts", "openapi.yaml")
with open(out, "w", encoding="utf-8") as f:
    yaml.safe_dump(app.openapi(), f, sort_keys=False, allow_unicode=True)
print("Đã ghi", os.path.normpath(out))
