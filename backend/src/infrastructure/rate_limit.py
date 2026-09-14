"""Rate limiting por IP y ruta (memory o Redis)."""
from __future__ import annotations

import ipaddress
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Protocol

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.infrastructure.config import settings


class RateLimitCounter(Protocol):
    def allow(self, key: str, limit: int, window_seconds: float) -> bool: ...


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


class RedisSlidingWindow:
    """Contador sliding window compartido entre réplicas (Redis sorted set)."""

    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    def allow(self, key: str, limit: int, window_seconds: float) -> bool:
        now = time.time()
        cutoff = now - window_seconds
        rkey = f"rl:{key}"
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(rkey, 0, cutoff)
        pipe.zcard(rkey)
        pipe.zadd(rkey, {f"{now}": now})
        pipe.expire(rkey, int(window_seconds) + 1)
        results = pipe.execute()
        count_before = int(results[1])
        return count_before < limit


# Orden: rutas IA específicas se resuelven en `_match_rule`.
_RULES_DOC = "see _match_rule"

def _match_rule(path: str, method: str) -> tuple[str, int, float] | None:
    if path.startswith("/api/v1/auth/register"):
        return ("/api/v1/auth/register", 5, 60.0)
    if path.startswith("/api/v1/auth/token"):
        return ("/api/v1/auth/token", 10, 60.0)
    if "/analyze" in path:
        return ("ia:analyze", 8, 60.0)
    if path.rstrip("/").endswith("/ask") or "/ask" in path:
        return ("ia:ask", 8, 60.0)
    if method == "POST" and "/quiz" in path and "/attempts" not in path:
        return ("ia:quiz", 8, 60.0)
    if path.startswith("/api/v1/documents/"):
        return ("/api/v1/documents/", 30, 60.0)
    if path.startswith("/api/v1/quizzes/"):
        return ("/api/v1/quizzes/", 20, 60.0)
    return None


def _parse_trusted_proxies(raw: str) -> list[ipaddress._BaseNetwork | ipaddress._BaseAddress]:
    out: list = []
    for part in (raw or "").split(","):
        token = part.strip()
        if not token:
            continue
        try:
            if "/" in token:
                out.append(ipaddress.ip_network(token, strict=False))
            else:
                out.append(ipaddress.ip_address(token))
        except ValueError:
            continue
    return out


def _client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    trusted = _parse_trusted_proxies(settings.TRUSTED_PROXIES)
    if not trusted:
        return peer
    try:
        peer_addr = ipaddress.ip_address(peer)
    except ValueError:
        return peer
    peer_ok = False
    for t in trusted:
        if isinstance(t, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
            if peer_addr in t:
                peer_ok = True
                break
        elif peer_addr == t:
            peer_ok = True
            break
    if not peer_ok:
        return peer
    xff = request.headers.get("x-forwarded-for") or ""
    if not xff:
        return peer
    return xff.split(",")[0].strip() or peer


def build_rate_limit_counter() -> RateLimitCounter:
    backend = (settings.RATE_LIMIT_BACKEND or "memory").lower().strip()
    if backend == "redis":
        import redis

        client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        client.ping()
        return RedisSlidingWindow(client)
    return SlidingWindowCounter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, counter: RateLimitCounter | None = None) -> None:
        super().__init__(app)
        self._counter = counter

    def _get_counter(self) -> RateLimitCounter:
        if self._counter is None:
            self._counter = build_rate_limit_counter()
        return self._counter

    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)
        rule = _match_rule(request.url.path, request.method.upper())
        if rule is None:
            return await call_next(request)
        prefix, limit, window = rule
        client = _client_ip(request)
        key = f"{client}:{prefix}"
        if not self._get_counter().allow(key, limit, window):
            return JSONResponse(
                status_code=429,
                content={"detail": "Demasiadas solicitudes. Intenta de nuevo más tarde."},
                headers={"Retry-After": "60"},
            )
        return await call_next(request)
