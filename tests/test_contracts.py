import httpx
from urllib.parse import urlsplit

from benchmark.validators import validate_contracts


def make_client(config, monkeypatch, mismatch=False, only_iaas=False):
    models = config["targets"]["targets"]

    for model in models:
        if only_iaas and model != "iaas":
            monkeypatch.delenv(model.upper() + "_URL", raising=False)
        else:
            monkeypatch.setenv(
                model.upper() + "_URL",
                f"https://{model}.example.test",
            )

    methods = []

    openapi_paths = {}
    for endpoint in config["targets"]["endpoints"].values():
        path = urlsplit(endpoint["path"]).path
        method = endpoint["method"].lower()
        openapi_paths.setdefault(path, {})[method] = {
            "responses": {
                "200": {"description": "OK"},
                "201": {"description": "Created"},
            }
        }

    def handler(request):
        methods.append(request.method)
        path = request.url.path

        if path == "/openapi.json":
            return httpx.Response(
                200,
                json={"paths": openapi_paths, "components": {"schemas": {}}},
            )

        if path.startswith("/items/"):
            item_id = path.rsplit("/", 1)[-1]
            return httpx.Response(
                200,
                json={"id": item_id, "name": "seed", "value": 1},
            )

        if path == "/compute":
            digest = "digest-faAs" if mismatch and request.url.host.startswith("faas") else "stable-digest"
            return httpx.Response(
                200,
                json={"digest": digest, "rounds": 1000},
            )

        if request.method == "POST":
            return httpx.Response(201, json={"id": "unexpected-write"})

        return httpx.Response(404, json={"detail": "not found"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return client, methods


def test_equivalent_contracts_pass(config, monkeypatch):
    client, methods = make_client(config, monkeypatch)
    with client:
        report = validate_contracts(config, client=client)

    assert report["passed"]
    assert "POST" not in methods
    assert report["scope"]["writes_executed"] is False


def test_deterministic_cpu_mismatch_blocks_official_run(config, monkeypatch):
    client, methods = make_client(config, monkeypatch, mismatch=True)
    with client:
        report = validate_contracts(config, client=client)

    assert not report["passed"]
    assert any("read-only payload" in message for message in report["errors"])
    assert "POST" not in methods


def test_iaas_can_be_validated_without_paas_or_faas(config, monkeypatch):
    client, methods = make_client(config, monkeypatch, only_iaas=True)
    with client:
        report = validate_contracts(
            config,
            models=["iaas"],
            client=client,
        )

    assert report["passed"]
    assert list(report["models"]) == ["iaas"]
    assert report["scope"]["equivalence_checked"] is False
    assert "POST" not in methods


def test_validator_never_executes_write_endpoint(config, monkeypatch):
    client, methods = make_client(config, monkeypatch)
    with client:
        report = validate_contracts(
            config,
            models=["iaas"],
            endpoints=["read", "cpu"],
            client=client,
        )

    assert report["passed"]
    assert "POST" not in methods
    assert all(method == "GET" for method in methods)


def test_write_endpoint_is_rejected_as_runtime_validator_scope(config, monkeypatch):
    client, _ = make_client(config, monkeypatch)
    with client:
        report = validate_contracts(
            config,
            models=["iaas"],
            endpoints=["write"],
            client=client,
        )

    assert not report["passed"]
    assert report["scope"]["writes_executed"] is False
