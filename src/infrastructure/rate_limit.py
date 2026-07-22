"""Rate limiting in-memory por IP y ruta (protección básica anti-abuso)."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.infrastructure.config import settings


class SlidingWindowCounter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_seconds: float) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            cutoff = now - window_seconds
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True


# path prefix → (max_requests, window_seconds)
# Orden: rutas IA más específicas primero (analyze/ask/quiz generation).
_RULES: list[tuple[str, int, float]] = [
    ("/api/v1/auth/register", 5, 60.0),
    ("/api/v1/auth/token", 10, 60.0),
    ("/api/v1/documents/", 12, 60.0),  # incluye analyze y ask (coste OpenAI)
    ("/api/v1/quizzes/", 12, 60.0),  # generate + attempts
]


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, counter: SlidingWindowCounter | None = None) -> None:
        super().__init__(app)
        self._counter = counter or SlidingWindowCounter()

    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)
        path = request.url.path
        client = request.client.host if request.client else "unknown"
        for prefix, limit, window in _RULES:
            if path.startswith(prefix) or path == prefix.rstrip("/"):
                key = f"{client}:{prefix}"
                if not self._counter.allow(key, limit, window):
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Demasiadas solicitudes. Intenta de nuevo más tarde."},
                        headers={"Retry-After": "60"},
                    )
                break
        return await call_next(request)
