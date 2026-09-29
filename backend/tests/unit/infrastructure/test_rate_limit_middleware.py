"""Cobertura middleware rate-limit y resolución de IP."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from starlette.requests import Request
from starlette.responses import Response

from src.infrastructure.config import settings
from src.infrastructure.rate_limit import (
    RateLimitMiddleware,
    SlidingWindowCounter,
    _client_ip,
    _match_rule,
    _parse_trusted_proxies,
)


def test_match_rule_auth_and_quizzes():
    assert _match_rule("/api/v1/auth/register", "POST") is not None
    assert _match_rule("/api/v1/auth/token", "POST") is not None
    assert _match_rule("/api/v1/quizzes/abc", "GET") is not None
    assert _match_rule("/unknown", "GET") is None


def test_parse_trusted_proxies_accepts_cidr_and_ip():
    parsed = _parse_trusted_proxies("127.0.0.1,10.0.0.0/8,bad-value")
    assert len(parsed) == 2


def test_client_ip_without_trusted_proxies():
    scope = {"type": "http", "method": "GET", "path": "/", "headers": [], "client": ("1.2.3.4", 1234)}
    req = Request(scope)
    assert _client_ip(req) == "1.2.3.4"


def test_client_ip_uses_xff_when_proxy_trusted(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "127.0.0.1")
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-forwarded-for", b"9.9.9.9, 1.2.3.4")],
        "client": ("127.0.0.1", 1234),
    }
    req = Request(scope)
    assert _client_ip(req) == "9.9.9.9"


@pytest.mark.asyncio
async def test_middleware_disabled_passes_through(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)

    async def app(scope, receive, send):
        resp = Response("ok")
        await resp(scope, receive, send)

    mw = RateLimitMiddleware(app)
    scope = {"type": "http", "method": "POST", "path": "/api/v1/documents/x/analyze", "headers": [], "client": ("1.1.1.1", 1)}
    req = Request(scope)

    called = False

    async def call_next(_request):
        nonlocal called
        called = True
        return Response("ok")

    resp = await mw.dispatch(req, call_next)
    assert called is True
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_middleware_returns_429_when_blocked(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    counter = SlidingWindowCounter()
    for _ in range(8):
        await counter.allow("1.1.1.1:ia:analyze", 8, 60.0)

    async def app(scope, receive, send):
        resp = Response("ok")
        await resp(scope, receive, send)

    mw = RateLimitMiddleware(app, counter=counter)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/documents/x/analyze",
        "headers": [],
        "client": ("1.1.1.1", 1),
    }
    req = Request(scope)

    resp = await mw.dispatch(req, AsyncMock(return_value=Response("ok")))
    assert resp.status_code == 429


def test_client_ip_untrusted_peer_ignores_xff(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "10.0.0.0/8")
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-forwarded-for", b"9.9.9.9")],
        "client": ("1.2.3.4", 1234),
    }
    assert _client_ip(Request(scope)) == "1.2.3.4"


def test_client_ip_trusted_without_xff_returns_peer(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "127.0.0.1")
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "client": ("127.0.0.1", 1234),
    }
    assert _client_ip(Request(scope)) == "127.0.0.1"


def test_client_ip_unknown_when_no_client(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "")
    scope = {"type": "http", "method": "GET", "path": "/", "headers": [], "client": None}
    assert _client_ip(Request(scope)) == "unknown"


@pytest.mark.asyncio
async def test_middleware_allows_when_under_limit(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    mw = RateLimitMiddleware(MagicMock(), counter=SlidingWindowCounter())
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/token",
        "headers": [],
        "client": ("2.2.2.2", 1),
    }
    resp = await mw.dispatch(Request(scope), AsyncMock(return_value=Response("ok")))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_sliding_window_evicts_expired_hits():
    """El reloj se parchea DENTRO del test, no con `monkeypatch`.

    `rate_limit.time` es el módulo `time` real: dejar el parche vivo hasta el
    teardown se lo aplica también al event loop, que agota el iterador.
    """
    from unittest.mock import patch

    from src.infrastructure.rate_limit import SlidingWindowCounter

    counter = SlidingWindowCounter()
    with patch(
        "src.infrastructure.rate_limit.time.monotonic",
        side_effect=[1000.0, 1070.0, 1070.0],
    ):
        assert await counter.allow("k", 1, 60.0) is True
        assert await counter.allow("k", 1, 60.0) is True


@pytest.mark.asyncio
async def test_redis_caido_degrada_al_contador_local(monkeypatch):
    """Un limitador caído no puede tumbar el borde.

    Antes `build_rate_limit_counter()` hacía `ping()` al construir —bloqueante y
    dentro del event loop— y propagaba el fallo como 500 en la ruta. Ahora la
    conexión es perezosa y el error degrada a conteo por proceso.
    """
    from src.infrastructure.rate_limit import RedisSlidingWindow, SlidingWindowCounter

    class ClienteCaido:
        def pipeline(self):
            raise ConnectionError("redis down")

    fallback = SlidingWindowCounter()
    counter = RedisSlidingWindow(ClienteCaido(), fallback=fallback)

    assert await counter.allow("k", 1, 60.0) is True
    # El plan B cuenta de verdad: la segunda pasada ya bloquea.
    assert await counter.allow("k", 1, 60.0) is False


@pytest.mark.asyncio
async def test_middleware_lazy_builds_counter(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "memory")
    mw = RateLimitMiddleware(MagicMock(), counter=None)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/documents/x/analyze",
        "headers": [],
        "client": ("1.1.1.1", 1),
    }
    resp = await mw.dispatch(Request(scope), AsyncMock(return_value=Response("ok")))
    assert resp.status_code == 200
    assert mw._get_counter() is not None
