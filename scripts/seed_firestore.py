"""Seed 100.000 bản ghi (seed=42) vào collection `items` của Firestore.

Điều kiện: đã chạy `gcloud auth application-default login` và Firestore đã được tạo.
    python scripts/seed_firestore.py --project <PROJECT_ID> [--count 100000]
Chạy lại an toàn (ghi đè cùng id với cùng dữ liệu). Cần: pip install google-cloud-firestore
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from google.cloud import firestore  # noqa: E402

from ccapi_core.service import gen_item, item_id  # noqa: E402
from ccapi_core.store import READ_COLLECTION  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--count", type=int, default=100_000)
    args = ap.parse_args()

    db = firestore.Client(project=args.project)
    col = db.collection(READ_COLLECTION)
    t0 = time.time()
    batch = db.batch()
    for i in range(1, args.count + 1):
        batch.set(col.document(item_id(i)), gen_item(i))
        if i % 500 == 0:  # giới hạn 500 thao tác mỗi batch
            batch.commit()
            batch = db.batch()
            if i % 10_000 == 0:
                print(f"  {i:,}/{args.count:,}  ({time.time() - t0:.0f}s)", flush=True)
    if args.count % 500:
        batch.commit()
    print(f"Xong {args.count:,} bản ghi trong {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
