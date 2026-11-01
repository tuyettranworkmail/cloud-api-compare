

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone

import functions_framework
from flask import jsonify, make_response

from ccapi_core import (
    ItemService,
    make_store,
    compute,
    DEFAULT_COMPUTE_ROUNDS,
    MAX_COMPUTE_ROUNDS,
)

service = ItemService(make_store())

INSTANCE_ID = os.getenv("INSTANCE_ID") or uuid.uuid4().hex[:12]
GIT_SHA = os.getenv("GIT_SHA", "dev")

_state_lock = threading.Lock()
_served = False



def validation_error():
    return jsonify({
        "error": {
            "code": "validation_error",
            "message": "Dữ liệu đầu vào không hợp lệ"
        }
    }), 422


def _handle_request(request):
    
    path = request.path

    item_path = (
        path.startswith("/items/")
        and path.count("/") == 2
        and bool(path.removeprefix("/items/"))
    )

    if path not in ("/health", "/compute", "/items") and not item_path:
        return jsonify({
            "error": {
                "code": "http_error",
                "message": "Not Found"
            }
        }), 404

    if path == "/items" and request.method != "POST":
        return jsonify({
            "error": {
                "code": "http_error",
                "message": "Method Not Allowed"
            }
        }), 405

    # POST: Tạo bản ghi mới
    if request.path == "/items" and request.method == "POST":
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return validation_error()

        name = data.get("name")
        category = data.get("category")
        value = data.get("value")
        payload = data.get("payload")

        if not (
            isinstance(name, str) and 1 <= len(name) <= 200
            and isinstance(category, str) and 1 <= len(category) <= 50
            and isinstance(value, int) and not isinstance(value, bool)
            and isinstance(payload, str) and len(payload) <= 2048
        ):
            return validation_error()

        key = request.headers.get("Idempotency-Key")
        item, created = service.create_item(data, key)

        return jsonify(item), 201 if created else 200

    # Các endpoint còn lại sử dụng GET
    if request.method != "GET":
        return jsonify({
            "error": {
                "code": "http_error",
                "message": "Method Not Allowed"
            }
        }), 405

    if request.path == "/health":
        return jsonify({"status": "ok"}), 200

    if request.path.startswith("/items/"):
        item_id = request.path.removeprefix("/items/")
        item = service.get_item(item_id)

        if item is None:
            return jsonify({
                "error": {
                    "code": "http_error",
                    "message": "Không tìm thấy bản ghi"
                }
            }), 404

        return jsonify(item), 200

    if request.path == "/compute":
        try:
            n = int(request.args.get("n", DEFAULT_COMPUTE_ROUNDS))
        except (ValueError, TypeError):
            n = 0

        if not 1 <= n <= MAX_COMPUTE_ROUNDS:
            return validation_error()

        return jsonify(compute(n)), 200

    return jsonify({
        "error": {
            "code": "http_error",
            "message": "Not Found"
        }
    }), 404
    
@functions_framework.http
def ccapi(request):
    global _served

    with _state_lock:
        cold = not _served
        _served = True

    start = time.perf_counter()

    try:
        response = make_response(_handle_request(request))
    except Exception:
        logging.exception("Unhandled FaaS request error")
        response = jsonify({
            "error": {
                "code": "internal_error",
                "message": "Internal Server Error"
            }
        })
        response.status_code = 500

    handler_ms = (time.perf_counter() - start) * 1000

    response.headers["X-Instance-Id"] = INSTANCE_ID
    response.headers["X-Cold-Start"] = "true" if cold else "false"
    response.headers["X-Handler-Ms"] = f"{handler_ms:.2f}"

    print(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z"),
        "model": "faas",
        "instance_id": INSTANCE_ID,
        "cold": cold,
        "endpoint": request.path,
        "status": response.status_code,
        "handler_ms": round(handler_ms, 2),
        "git_sha": GIT_SHA
    }), flush=True)

    return response

