"""Optional ASGI middleware: process-first request is NOT infrastructure cold start."""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid

from benchmark.io import utcnow


class BenchmarkMiddleware:
    def __init__(self, app, deployment_model: str):
        self.app = app
        self.model = deployment_model
        self.instance_id = uuid.uuid4().hex
        self.first = True
        self.lock = threading.Lock()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        with self.lock:
            first, self.first = self.first, False
        start = time.perf_counter()
        headers = dict(scope.get("headers", []))
        request_id = headers.get(b"x-request-id", b"").decode("utf-8", errors="replace")[:200] or uuid.uuid4().hex
        status = 500

        async def wrapped_send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message["headers"] = list(message.get("headers", [])) + [
                    (b"x-instance-id", self.instance_id.encode()),
                    (b"x-cold-start", str(first).lower().encode()),
                    (b"x-handler-duration-ms", f"{(time.perf_counter() - start) * 1000:.3f}".encode()),
                ]
            await send(message)
        try:
            await self.app(scope, receive, wrapped_send)
        finally:
            logging.getLogger("benchmark.requests").info(json.dumps({
                "timestamp": utcnow(), "request_id": request_id, "instance_id": self.instance_id,
                "deployment_model": self.model, "endpoint": scope.get("path"), "cold_start": first,
                "handler_duration_ms": (time.perf_counter() - start) * 1000, "status_code": status,
                "cold_start_scope": "process_first_request",
            }))
