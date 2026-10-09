"""Gzip en la API, salvo voz y originales (que ya vienen comprimidos) y SSE."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _h(c):
    s = uuid4().hex[:8]
    e = f"z_{s}@example.com"
    c.post("/api/v1/auth/register", json={"username": f"z_{s}", "email": e, "password": "Clave123"})
    return {"Authorization": "Bearer " + c.post("/api/v1/auth/token", data={"username": e, "password": "Clave123"}).json()["access_token"], "Accept-Encoding": "gzip"}


def test_una_respuesta_json_grande_va_comprimida(client):
    h = _h(client)
    chat = client.post("/api/v1/chats/", headers=h, json={}).json()["id"]
    for i in range(6):
        client.post(f"/api/v1/chats/{chat}/messages", headers=h, json={"role": "system", "content": "Nota larga de prueba. " * 40})

    r = client.get(f"/api/v1/chats/{chat}", headers=h)

    assert r.headers.get("content-encoding") == "gzip"
    assert len(r.json()["messages"]) == 6, "el cliente la recibe igual"


def test_las_respuestas_pequenas_siguen_llegando_bien(client):
    r = client.get("/health", headers={"Accept-Encoding": "gzip"})

    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_sin_accept_encoding_no_se_comprime(client):
    assert client.get("/health", headers={"Accept-Encoding": "identity"}).headers.get("content-encoding") is None


def test_el_original_de_un_documento_no_se_recomprime(client):
    h = _h(client)
    doc = client.post("/api/v1/documents/upload", headers=h, files={"file": ("a.txt", "Texto de prueba largo. " * 200, "text/plain")}).json()

    r = client.get(f"/api/v1/documents/{doc['id']}/content", headers=h)

    assert r.status_code == 200 and r.headers.get("content-encoding") is None
