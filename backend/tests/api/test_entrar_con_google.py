"""POST /auth/google: entrar con Google, vincular cuentas y borrar confirmando con Google (ADR-025)."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.domain.ports.external_identity import (
    ExternalIdentity,
    ExternalIdentityVerifier,
    InvalidExternalToken,
)
from src.interfaces.api import dependencies as deps
from src.main import app
from tests.conftest import clear_dependency_caches


class GoogleFalso(ExternalIdentityVerifier):
    """El "token" es el correo: los tests deciden qué identidad devuelve Google."""

    async def verify(self, token: str) -> ExternalIdentity:
        if not token.startswith("ok:"):
            raise InvalidExternalToken("El inicio de sesión con Google no es válido.")
        correo = token[3:].split("|")[0]
        return ExternalIdentity(subject=f"sub-{correo}", email=correo, name="Ana Pérez")


@pytest.fixture
def client():
    clear_dependency_caches()
    app.dependency_overrides[deps.get_google_verifier] = lambda: GoogleFalso()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    clear_dependency_caches()


def _correo():
    return f"g_{uuid4().hex[:8]}@gmail.com"


def _tok(correo):
    return f"ok:{correo}|" + "x" * 20


def _google(c, correo):
    return c.post("/api/v1/auth/google", json={"id_token": _tok(correo)})


def test_crea_la_cuenta_y_da_sesion(client):
    correo = _correo()

    r = _google(client, correo)

    assert r.status_code == 200, r.text
    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).json()
    assert me["email"] == correo and me["email_verified"] is True and me["has_password"] is False


def test_entrar_dos_veces_es_la_misma_cuenta(client):
    correo = _correo()
    h1 = {"Authorization": f"Bearer {_google(client, correo).json()['access_token']}"}
    h2 = {"Authorization": f"Bearer {_google(client, correo).json()['access_token']}"}

    assert client.get("/api/v1/users/me", headers=h1).json()["id"] == client.get("/api/v1/users/me", headers=h2).json()["id"]


def test_un_token_invalido_es_401(client):
    assert client.post("/api/v1/auth/google", json={"id_token": "malo" + "x" * 30}).status_code == 401


def test_una_cuenta_sin_verificar_se_vincula_y_pierde_la_contrasena_del_pre_registro(client):
    """Secuestro por pre-registro: alguien registró el correo de otra persona con su
    contraseña. Cuando la dueña entra con Google, esa contraseña deja de servir."""
    correo = _correo()
    client.post("/api/v1/auth/register", json={"username": f"u{uuid4().hex[:6]}", "email": correo, "password": "Clave123"})

    assert _google(client, correo).status_code == 200
    r = client.post("/api/v1/auth/token", data={"username": correo, "password": "Clave123"})
    assert r.status_code == 401


def test_las_cuentas_de_google_no_entran_con_contrasena(client):
    correo = _correo()
    _google(client, correo)

    r = client.post("/api/v1/auth/token", data={"username": correo, "password": "!sin-contrasena"})
    assert r.status_code == 401


def test_borrar_la_cuenta_confirmando_con_google(client):
    correo = _correo()
    h = {"Authorization": f"Bearer {_google(client, correo).json()['access_token']}"}

    otro = client.request("DELETE", "/api/v1/users/me", headers=h, json={"google_id_token": _tok(_correo())})
    assert otro.status_code == 403, "otra cuenta de Google no confirma"
    assert client.request("DELETE", "/api/v1/users/me", headers=h, json={}).status_code == 422
    assert client.request("DELETE", "/api/v1/users/me", headers=h, json={"google_id_token": _tok(correo)}).status_code == 204
    assert client.get("/api/v1/users/me", headers=h).status_code == 401


def test_providers_dice_si_google_esta_configurado(client, monkeypatch):
    from src.infrastructure.config import settings

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(settings, "CLERK_PUBLISHABLE_KEY", "")
    assert client.get("/api/v1/auth/providers").json() == {
        "google_client_id": None,
        "clerk_publishable_key": None,
    }
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "123.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "CLERK_PUBLISHABLE_KEY", "pk_test_publica")
    cuerpo = client.get("/api/v1/auth/providers").json()
    assert cuerpo == {
        "google_client_id": "123.apps.googleusercontent.com",
        "clerk_publishable_key": "pk_test_publica",
    }
    assert "sk_" not in str(cuerpo)
