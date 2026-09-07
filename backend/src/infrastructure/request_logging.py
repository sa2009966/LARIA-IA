"""Middleware de logging de requests HTTP (sin cuerpos ni tokens)."""
from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("laria.http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        started = time.perf_counter()
        path = request.url.path
        method = request.method
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            logger.exception(
                "request_failed method=%s path=%s request_id=%s duration_ms=%.1f",
                method,
                path,
                request_id,
                elapsed_ms,
            )
            raise
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        response.headers["X-Request-Id"] = request_id
        # /health, /ready y /metrics a DEBUG para no saturar probes
        log = logger.debug if path in {"/health", "/ready", "/metrics"} else logger.info
        log(
            "request method=%s path=%s status=%s request_id=%s duration_ms=%.1f",
            method,
            path,
            response.status_code,
            request_id,
            elapsed_ms,
        )
        return response
