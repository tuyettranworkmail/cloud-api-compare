"""Adapter FastAPI cho IaaS và PaaS (cùng một Docker image).

Hợp đồng API: xem contracts/openapi.yaml. Mọi phản hồi có 3 header:
X-Instance-Id, X-Cold-Start, X-Handler-Ms. Mỗi request ghi 1 dòng log JSON.
"""
import json
import os
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ccapi_core import DEFAULT_COMPUTE_ROUNDS, MAX_COMPUTE_ROUNDS, ItemService, compute, make_store

MODEL = os.getenv("MODEL", "paas")  # iaas | paas | faas
GIT_SHA = os.getenv("GIT_SHA", "dev")
INSTANCE_ID = os.getenv("INSTANCE_ID") or uuid.uuid4().hex[:12]

app = FastAPI(title="ccapi", version="1.0.0")
service = ItemService(make_store())
_state = {"served": False}


class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=50)
    value: int
    payload: str = Field(max_length=2048)


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(HTTPException)
async def http_exc(_: Request, exc: HTTPException):
    return error(exc.status_code, "http_error", str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_exc(_: Request, exc: RequestValidationError):
    return error(422, "validation_error", "Dữ liệu đầu vào không hợp lệ")


@app.middleware("http")
async def observe(request: Request, call_next):
    cold = not _state["served"]
    _state["served"] = True
    t0 = time.perf_counter()
    response = await call_next(request)
    handler_ms = (time.perf_counter() - t0) * 1000
    response.headers["X-Instance-Id"] = INSTANCE_ID
    response.headers["X-Cold-Start"] = "true" if cold else "false"
    response.headers["X-Handler-Ms"] = f"{handler_ms:.2f}"
    route = request.scope.get("route")
    print(
        json.dumps(
            {
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                "model": MODEL,
                "instance_id": INSTANCE_ID,
                "cold": cold,
                "endpoint": route.path if route else request.url.path,
                "status": response.status_code,
                "handler_ms": round(handler_ms, 2),
                "git_sha": GIT_SHA,
            }
        ),
        flush=True,
    )
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/items/{item_id}")
def get_item(item_id: str):
    item = service.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi")
    return item


@app.post(
    "/items",
    status_code=201,
    responses={200: {"description": "Trùng Idempotency-Key: trả lại bản ghi đã có, không ghi đôi"}},
)
def create_item(body: ItemIn, idempotency_key: str | None = Header(default=None)):
    item, created = service.create_item(body.model_dump(), idempotency_key)
    return JSONResponse(status_code=201 if created else 200, content=item)


@app.get("/compute")
def run_compute(n: int = Query(default=DEFAULT_COMPUTE_ROUNDS, ge=1, le=MAX_COMPUTE_ROUNDS)):
    return compute(n)
