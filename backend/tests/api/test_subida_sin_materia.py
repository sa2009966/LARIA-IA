"""Subir desde el chat, que solo manda `file` (sin `subject`).

`subject` era obligatorio en /documents/upload y el chat nunca lo pregunta: toda
subida desde el chat daba 422 "Field required" y el toast lo mostraba tal cual.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.main import app
from tests.conftest import clear_dependency_caches


@pytest.fixture
def client():
    clear_dependency_caches()
    with TestClient(app) as c:
        yield c
    clear_dependency_caches()


def _auth(c):
    s = uuid4().hex[:8]
    email = f"sub_{s}@example.com"
    c.post("/api/v1/auth/register", json={"username": f"sub_{s}", "email": email, "password": "SecurePass1x"})
    tok = c.post("/api/v1/auth/token", data={"username": email, "password": "SecurePass1x"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_multipart_solo_con_el_archivo_sube_como_general(client):
    h = _auth(client)

    r = client.post("/api/v1/documents/upload", headers=h,
                    files={"file": ("apuntes.txt", "La mitosis es la división celular. " * 20, "text/plain")})

    assert r.status_code == 201, r.text
    assert r.json()["subject"] == "General"


def test_json_sin_materia_tambien(client):
    h = _auth(client)

    r = client.post("/api/v1/documents/", headers=h, json={"filename": "a.txt", "content": "La célula. " * 20})

    assert r.status_code == 201, r.text
    assert r.json()["subject"] == "General"


def test_una_materia_valida_se_respeta(client):
    h = _auth(client)

    r = client.post("/api/v1/documents/upload", headers=h, data={"subject": "Historia"},
                    files={"file": ("a.txt", "Roma fue fundada en el 753 a. C. " * 20, "text/plain")})

    assert r.json()["subject"] == "Historia"


def test_general_no_filtra_heuristicas_por_area():
    """Sin área reconocida no se filtra nada: fijar "Matemática" sí contaminaría."""
    from src.domain.subject_areas import area_of_subject

    assert area_of_subject("General") is None
