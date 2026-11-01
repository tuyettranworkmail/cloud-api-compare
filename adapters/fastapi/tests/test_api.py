import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "core"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("STORE", "memory")

from fastapi.testclient import TestClient  # noqa: E402

from app import app  # noqa: E402

client = TestClient(app)
BODY = {"name": "a", "category": "cat-01", "value": 5, "payload": "p"}


def test_health_and_headers_and_cold_flag():
    r1 = client.get("/health")
    assert r1.status_code == 200 and r1.json() == {"status": "ok"}
    assert r1.headers["X-Instance-Id"]
    assert float(r1.headers["X-Handler-Ms"]) >= 0
    # Test có thể không phải request đầu tiên của process; chỉ kiểm tra giá trị hợp lệ
    assert r1.headers["X-Cold-Start"] in ("true", "false")
    assert client.get("/health").headers["X-Cold-Start"] == "false"


def test_get_item_ok_and_404():
    r = client.get("/items/item-000001")
    assert r.status_code == 200 and r.json()["id"] == "item-000001"
    r = client.get("/items/item-999999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "http_error"


def test_post_item_201_then_idempotent_200():
    r = client.post("/items", json=BODY, headers={"Idempotency-Key": "k-1"})
    assert r.status_code == 201 and r.json()["id"] == "k-1"
    r2 = client.post("/items", json=BODY, headers={"Idempotency-Key": "k-1"})
    assert r2.status_code == 200 and r2.json()["id"] == "k-1"
    r3 = client.post("/items", json=BODY)
    assert r3.status_code == 201 and r3.json()["id"] != "k-1"


def test_post_validation_error():
    r = client.post("/items", json={"name": "a"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_compute():
    r = client.get("/compute?n=1000")
    assert r.status_code == 200 and r.json()["rounds"] == 1000
    assert client.get("/compute?n=0").status_code == 422
    assert client.get("/compute").json()["rounds"] == 200000
