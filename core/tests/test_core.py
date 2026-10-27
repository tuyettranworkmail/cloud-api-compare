import hashlib

import pytest

from ccapi_core import ItemService, MemoryStore, compute, gen_item


def test_compute_is_deterministic():
    assert compute(1000) == compute(1000)
    d = b"ccapi"
    for _ in range(3):
        d = hashlib.sha256(d).digest()
    assert compute(3)["digest"] == d.hex()


def test_compute_bounds():
    with pytest.raises(ValueError):
        compute(0)
    with pytest.raises(ValueError):
        compute(10**9)


def test_gen_item_is_deterministic_and_512_bytes():
    a, b = gen_item(7), gen_item(7)
    assert a == b
    assert len(a["payload"]) == 512
    assert gen_item(7) != gen_item(8)


def test_get_item():
    svc = ItemService(MemoryStore(seed_count=10))
    assert svc.get_item("item-000001")["category"].startswith("cat-")
    assert svc.get_item("item-999999") is None


def test_create_item_and_idempotency():
    svc = ItemService(MemoryStore(seed_count=10))
    body = {"name": "x", "category": "cat-01", "value": 1, "payload": "p"}
    r1, created1 = svc.create_item(body, "key-1")
    r2, created2 = svc.create_item(body, "key-1")
    assert created1 is True and created2 is False
    assert r1["id"] == r2["id"] == "key-1"
    r3, created3 = svc.create_item(body)
    assert created3 is True and r3["id"] != "key-1"
