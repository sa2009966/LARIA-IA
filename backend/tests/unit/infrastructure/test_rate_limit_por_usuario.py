"""Límites por usuario y por cuenta, no por IP compartida.

En Render la IP que ve la app es la del balanceador: contando por IP, cada
límite era global (10 logins/min para todos). Y los mensajes del chat, que son
llamadas al modelo, no tenían límite.
"""
from unittest.mock import AsyncMock

import jwt
import pytest
from starlette.requests import Request
from starlette.responses import Response

from src.infrastructure import rate_limit as rl
from src.infrastructure.config import JWT_ALGORITHM, settings


def _req(path="/api/v1/chats/x/messages", token=None, ip="10.0.0.1", method="POST"):
    headers = [(b"authorization", f"Bearer {token}".encode())] if token else []
    return Request({"type": "http", "method": method, "path": path, "headers": headers, "client": (ip, 1)})


def _token(sub):
    return jwt.encode({"sub": sub}, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def test_con_token_valido_la_clave_es_el_usuario():
    assert rl._client_key(_req(token=_token("abc"))) == "u:abc"


def test_un_token_falsificado_cae_a_la_ip():
    falso = jwt.encode({"sub": "otro"}, "x" * 40, algorithm=JWT_ALGORITHM)

    assert rl._client_key(_req(token=falso)) == "ip:10.0.0.1"


@pytest.mark.parametrize("ruta", ["/api/v1/chats/abc/messages", "/api/v1/chats/abc/stream"])
def test_los_mensajes_del_chat_tienen_limite(ruta):
    assert rl._match_rule(ruta, "POST")[0] == "ia:chat"


@pytest.mark.asyncio
async def test_dos_usuarios_detras_de_la_misma_ip_no_se_bloquean_entre_si(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    mw = rl.RateLimitMiddleware(AsyncMock(), counter=rl.SlidingWindowCounter())
    siguiente = AsyncMock(return_value=Response("ok"))

    for _ in range(20):
        assert (await mw.dispatch(_req(token=_token("ana")), siguiente)).status_code == 200
    assert (await mw.dispatch(_req(token=_token("ana")), siguiente)).status_code == 429
    assert (await mw.dispatch(_req(token=_token("beto")), siguiente)).status_code == 200


@pytest.mark.asyncio
async def test_el_login_se_limita_por_cuenta(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(rl, "_shared_counter", rl.SlidingWindowCounter())

    for _ in range(rl.LOGIN_ATTEMPTS_PER_ACCOUNT):
        assert await rl.login_attempt_allowed("Ana@Example.com")
    assert not await rl.login_attempt_allowed("ana@example.com"), "mayúsculas no esquivan el límite"
    assert await rl.login_attempt_allowed("beto@example.com"), "bloquear una cuenta no bloquea otras"
