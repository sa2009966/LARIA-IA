"""Suite API: auth, JWT y ownership vía TestClient."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.interfaces.api import dependencies as deps
from src.main import app


def _clear_caches() -> None:
    deps.get_user_repo.cache_clear()
    deps.get_document_repo.cache_clear()
    deps.get_quiz_repo.cache_clear()
    deps.get_attempt_repo.cache_clear()
    deps.get_interaction_repo.cache_clear()
    deps.get_ia_analyst.cache_clear()
    deps.get_event_bus.cache_clear()


@pytest.fixture
def client():
    _clear_caches()
    with TestClient(app) as c:
        yield c
    _clear_caches()


def _register(client: TestClient, email: str, username: str, password: str = "SecurePass1x"):
    return client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )


def _token(client: TestClient, email: str, password: str = "SecurePass1x") -> str:
    r = client.post(
        "/api/v1/auth/token",
        data={"username": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


class TestAuthApi:
    def test_register_token_me(self, client: TestClient):
        email = f"ana_{uuid4().hex[:8]}@example.com"
        r = _register(client, email, f"ana_{uuid4().hex[:6]}")
        assert r.status_code == 201
        token = _token(client, email)
        me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["email"] == email

    def test_me_sin_token_401(self, client: TestClient):
        r = client.get("/api/v1/users/me")
        assert r.status_code == 401

    def test_token_invalido_401(self, client: TestClient):
        r = client.get("/api/v1/users/me", headers={"Authorization": "Bearer not-a-jwt"})
        assert r.status_code == 401

    def test_student_no_lista_usuarios(self, client: TestClient):
        email = f"stu_{uuid4().hex[:8]}@example.com"
        _register(client, email, f"stu_{uuid4().hex[:6]}")
        token = _token(client, email)
        r = client.get("/api/v1/users/", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403

    def test_register_conflicto_generico(self, client: TestClient):
        email = f"dup_{uuid4().hex[:8]}@example.com"
        user = f"dup_{uuid4().hex[:6]}"
        assert _register(client, email, user).status_code == 201
        r = _register(client, email, f"otro_{uuid4().hex[:6]}")
        assert r.status_code == 409
        assert "email=" not in r.json()["detail"]
        assert "username=" not in r.json()["detail"]


class TestDocumentsOwnershipApi:
    def test_upload_and_list(self, client: TestClient):
        email = f"doc_{uuid4().hex[:8]}@example.com"
        _register(client, email, f"doc_{uuid4().hex[:6]}")
        token = _token(client, email)
        headers = {"Authorization": f"Bearer {token}"}
        up = client.post(
            "/api/v1/documents/",
            headers=headers,
            json={"filename": "t.txt", "content": "hola mundo educativo", "subject": "Historia"},
        )
        assert up.status_code == 201, up.text
        body = up.json()
        assert body["status"] == "uploaded"
        assert body["has_analysis"] is False

        listed = client.get("/api/v1/documents/", headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()) == 1

    def test_documento_ajeno_404(self, client: TestClient):
        a_email = f"a_{uuid4().hex[:8]}@example.com"
        b_email = f"b_{uuid4().hex[:8]}@example.com"
        _register(client, a_email, f"a_{uuid4().hex[:6]}")
        _register(client, b_email, f"b_{uuid4().hex[:6]}")
        token_a = _token(client, a_email)
        token_b = _token(client, b_email)

        up = client.post(
            "/api/v1/documents/",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"filename": "t.txt", "content": "contenido", "subject": "Historia"},
        )
        doc_id = up.json()["id"]
        r = client.get(
            f"/api/v1/documents/{doc_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert r.status_code == 404
        assert r.json()["detail"] == "Recurso no encontrado"
