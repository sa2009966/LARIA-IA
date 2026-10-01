"""Swagger en producción: detrás de usuario y contraseña, no público (ADR-024)."""
import base64
import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    from src.infrastructure.config import settings
    import src.main as main

    monkeypatch.setattr(settings, "ENABLE_DOCS", False)
    monkeypatch.setattr(settings, "DOCS_PASSWORD", "secreta-de-prueba")
    importlib.reload(main)  # las rutas de docs se deciden al montar la app
    with TestClient(main.app) as c:
        yield c
    monkeypatch.undo()
    importlib.reload(main)


def _basic(u, p):
    return {"Authorization": "Basic " + base64.b64encode(f"{u}:{p}".encode()).decode()}


def test_sin_credenciales_pide_usuario_y_contrasena(client):
    r = client.get("/docs")

    assert r.status_code == 401 and r.headers["www-authenticate"].startswith("Basic")
    assert client.get("/openapi.json").status_code == 401


def test_con_la_contrasena_mala_no(client):
    assert client.get("/docs", headers=_basic("laria", "otra")).status_code == 401


def test_con_las_buenas_se_ven_los_metodos(client):
    h = _basic("laria", "secreta-de-prueba")

    assert client.get("/docs", headers=h).status_code == 200
    spec = client.get("/openapi.json", headers=h).json()
    assert "/api/v1/chats/" in spec["paths"]
