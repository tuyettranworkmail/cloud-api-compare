import httpx

from benchmark.validators import validate_contracts


def make_client(config, monkeypatch, mismatch=False):
    for model in config["targets"]["targets"]:
        monkeypatch.setenv(model.upper() + "_URL", f"https://{model}.example.test")
    def handler(request):
        path = request.url.path
        if path == "/openapi.json":
            return httpx.Response(200, json={"paths": {ep.get("openapi_path", ep["path"]): {ep["method"].lower(): {"responses": {"200": {}}}} for ep in config["targets"]["endpoints"].values()}})
        if path.startswith("/items/"):
            return httpx.Response(200, json={"id": path.split("/")[-1], "name": "seed", "category": "cat-00", "value": 1, "payload": "x", "created_at": "2026-01-01T00:00:00Z"})
        if path == "/items":
            return httpx.Response(201, json={"id": "generated", "name": "benchmark", "category": "cat-00", "value": 42, "payload": "x", "created_at": "2026-01-01T00:00:00Z"})
        return httpx.Response(200, json={"digest": "bad" if mismatch and request.url.host.startswith("faas") else "ok", "rounds": 65000})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_equivalent_contracts_pass(config, monkeypatch):
    with make_client(config, monkeypatch) as client:
        assert validate_contracts(config, allow_writes=True, client=client)["passed"]


def test_deterministic_cpu_mismatch_blocks_official_run(config, monkeypatch):
    with make_client(config, monkeypatch, mismatch=True) as client:
        report = validate_contracts(config, allow_writes=True, client=client)
    assert not report["passed"]
    assert any("payload/CPU" in message for message in report["errors"])


def test_writes_not_silently_authorized(config, monkeypatch):
    with make_client(config, monkeypatch) as client:
        assert not validate_contracts(config, allow_writes=False, client=client)["passed"]
