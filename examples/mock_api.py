"""LOCAL_TEST_ONLY contract fixture; not the team's API and never a GCP benchmark."""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from benchmark.instrumentation import BenchmarkMiddleware


class Item(BaseModel):
    id: str
    name: str
    value: int


class WriteItem(Item):
    benchmark_run_id: str


class Created(BaseModel):
    id: str


class CPUInput(BaseModel):
    iterations: int = Field(default=10000, ge=1, le=1000000)


class CPUResult(BaseModel):
    result: int


def create_app() -> FastAPI:
    app = FastAPI(title="Local benchmark contract fixture")
    app.add_middleware(BenchmarkMiddleware, deployment_model=os.environ.get("MOCK_MODEL", "iaas"))
    store = {f"item-{i:06}": {"id": f"item-{i:06}", "name": f"seed-{i}", "value": i} for i in range(1, 4)}

    @app.get("/api/items/{id}", response_model=Item)
    def read(id: str):
        if id not in store:
            raise HTTPException(404)
        return store[id]

    @app.post("/api/items", status_code=201, response_model=Created)
    def write(item: WriteItem):
        if not item.id.startswith("bench-"):
            raise HTTPException(422, "Fixture chỉ chấp nhận benchmark namespace")
        if item.id in store:
            raise HTTPException(409)
        store[item.id] = item.model_dump()
        return {"id": item.id}

    @app.post("/api/cpu", response_model=CPUResult)
    def cpu(payload: CPUInput):
        value = 0
        for i in range(payload.iterations):
            value = (value + i * i) % 1000000007
        return {"result": value}
    return app
