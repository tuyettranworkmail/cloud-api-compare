"""Hiệu chỉnh số vòng băm n cho /compute: mục tiêu 50-100 ms trên 1 vCPU.

Chạy TRÊN MÁY ĐÍCH (VM hoặc container đã giới hạn --cpus=1), không chạy trên laptop:
    docker run --rm --cpus=1 --memory=1g -v "$PWD":/w -w /w python:3.12-slim \
        python scripts/calibrate_compute.py
Sau đó sửa DEFAULT_COMPUTE_ROUNDS trong core/ccapi_core/service.py và đóng băng.
"""
import hashlib
import statistics
import sys
import time


def run(n: int) -> float:
    d = b"ccapi"
    t0 = time.perf_counter()
    for _ in range(n):
        d = hashlib.sha256(d).digest()
    return (time.perf_counter() - t0) * 1000


def main(target_ms: float = 75.0):
    run(50_000)  # làm nóng
    n = 100_000
    for _ in range(6):
        ms = statistics.median(run(n) for _ in range(5))
        print(f"n={n:>9,}  median={ms:7.1f} ms")
        n = int(n * target_ms / ms)
    print(f"\nGợi ý DEFAULT_COMPUTE_ROUNDS ≈ {n:,} (mục tiêu {target_ms:.0f} ms)")


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 75.0)
