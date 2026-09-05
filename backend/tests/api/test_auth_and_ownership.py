"""Suite API: auth, JWT y ownership vía TestClient."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.infrastructure.config import settings
from src.main import app
from tests.conftest import clear_dependency_caches


@pytest.fixture
def client():
    clear_dependency_caches()
    with TestClient(app) as c:
        yield c
    clear_dependency_caches()


@pytest.fixture
def admin_client(monkeypatch: pytest.MonkeyPatch):
    """TestClient con admin creado en lifespan (ADMIN_EMAIL/PASSWORD)."""
    email = f"adm_{uuid4().hex[:8]}@example.com"
    monkeypatch.setattr(settings, "ADMIN_EMAIL", email)
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", "SecurePass1x")
    monkeypatch.setattr(settings, "ADMIN_USERNAME", f"adm_{uuid4().hex[:6]}")
    clear_dependency_caches()
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        yield c, email
    app.dependency_overrides.clear()
    clear_dependency_caches()


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


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestAuthApi:
    def test_register_token_me(self, client: TestClient):
        email = f"ana_{uuid4().hex[:8]}@example.com"
        r = _register(client, email, f"ana_{uuid4().hex[:6]}")
        assert r.status_code == 201
        token = _token(client, email)
        me = client.get("/api/v1/users/me", headers=_auth_header(token))
        assert me.status_code == 200
        assert me.json()["email"] == email

    def test_me_sin_token_401(self, client: TestClient):
        r = client.get("/api/v1/users/me")
        assert r.status_code == 401

    def test_token_invalido_401(self, client: TestClient):
        r = client.get("/api/v1/users/me", headers={"Authorization": "Bearer not-a-jwt"})
        assert r.status_code == 401

    def test_token_credenciales_invalidas_401(self, client: TestClient):
        r = client.post(
            "/api/v1/auth/token",
            data={"username": "nobody@example.com", "password": "SecurePass1x"},
        )
        assert r.status_code == 401

    def test_admin_lista_usuarios_200(self, admin_client):
        client, admin_email = admin_client
        admin_token = _token(client, admin_email)
        stu_email = f"stu_{uuid4().hex[:8]}@example.com"
        assert _register(client, stu_email, f"stu_{uuid4().hex[:6]}").status_code == 201
        r = client.get("/api/v1/users/", headers=_auth_header(admin_token))
        assert r.status_code == 200, r.text
        emails = {u["email"] for u in r.json()}
        assert admin_email in emails
        assert stu_email in emails
        for u in r.json():
            assert "password" not in u
            assert "hashed_password" not in u
        email = f"stu_{uuid4().hex[:8]}@example.com"
        _register(client, email, f"stu_{uuid4().hex[:6]}")
        token = _token(client, email)
        r = client.get("/api/v1/users/", headers=_auth_header(token))
        assert r.status_code == 403

    def test_register_conflicto_generico(self, client: TestClient):
        email = f"dup_{uuid4().hex[:8]}@example.com"
        user = f"dup_{uuid4().hex[:6]}"
        assert _register(client, email, user).status_code == 201
        r = _register(client, email, f"otro_{uuid4().hex[:6]}")
        assert r.status_code == 409
        assert "email=" not in r.json()["detail"]
        assert "username=" not in r.json()["detail"]

    def test_learning_sin_token_401(self, client: TestClient):
        assert client.get("/api/v1/learning/me").status_code == 401
        assert client.get("/api/v1/learning/me/profile").status_code == 401

    def test_documents_routes_sin_token_401(self, client: TestClient):
        doc_id = uuid4()
        assert client.post(
            "/api/v1/documents/",
            json={"filename": "t.txt", "content": "hola", "subject": "Historia"},
        ).status_code == 401
        assert client.post("/api/v1/documents/upload").status_code == 401
        assert client.get("/api/v1/documents/").status_code == 401
        assert client.get(f"/api/v1/documents/{doc_id}").status_code == 401
        assert client.delete(f"/api/v1/documents/{doc_id}").status_code == 401
        assert client.post(f"/api/v1/documents/{doc_id}/analyze").status_code == 401
        assert client.post(
            f"/api/v1/documents/{doc_id}/ask",
            json={"question": "¿De qué trata?"},
        ).status_code == 401
        assert client.post(f"/api/v1/documents/{doc_id}/quiz").status_code == 401

    def test_quizzes_routes_sin_token_401(self, client: TestClient):
        quiz_id = uuid4()
        assert client.get(f"/api/v1/quizzes/{quiz_id}").status_code == 401
        assert client.post(
            f"/api/v1/quizzes/{quiz_id}/attempts",
            json={"answers": {"0": "A"}},
        ).status_code == 401

    def test_admin_delete_user_204_y_jwt_inactivo_401(self, admin_client):
        client, admin_email = admin_client
        admin_token = _token(client, admin_email)
        stu_email = f"stu_{uuid4().hex[:8]}@example.com"
        assert _register(client, stu_email, f"stu_{uuid4().hex[:6]}").status_code == 201
        stu_token = _token(client, stu_email)
        me = client.get("/api/v1/users/me", headers=_auth_header(stu_token))
        assert me.status_code == 200
        user_id = me.json()["id"]

        deleted = client.delete(
            f"/api/v1/users/{user_id}",
            headers=_auth_header(admin_token),
        )
        assert deleted.status_code == 204

        inactive = client.get("/api/v1/users/me", headers=_auth_header(stu_token))
        assert inactive.status_code == 401

    def test_student_no_borra_usuario_403(self, client: TestClient):
        email = f"stu_{uuid4().hex[:8]}@example.com"
        assert _register(client, email, f"stu_{uuid4().hex[:6]}").status_code == 201
        token = _token(client, email)
        me = client.get("/api/v1/users/me", headers=_auth_header(token))
        r = client.delete(
            f"/api/v1/users/{me.json()['id']}",
            headers=_auth_header(token),
        )
        assert r.status_code == 403

    def test_admin_delete_usuario_inexistente_404(self, admin_client):
        client, admin_email = admin_client
        admin_token = _token(client, admin_email)
        missing = uuid4()
        r = client.delete(
            f"/api/v1/users/{missing}",
            headers=_auth_header(admin_token),
        )
        assert r.status_code == 404


class TestDocumentsOwnershipApi:
    def test_upload_and_list(self, client: TestClient):
        email = f"doc_{uuid4().hex[:8]}@example.com"
        _register(client, email, f"doc_{uuid4().hex[:6]}")
        token = _token(client, email)
        headers = _auth_header(token)
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
            headers=_auth_header(token_a),
            json={"filename": "t.txt", "content": "contenido", "subject": "Historia"},
        )
        doc_id = up.json()["id"]
        r = client.get(
            f"/api/v1/documents/{doc_id}",
            headers=_auth_header(token_b),
        )
        assert r.status_code == 404
        assert r.json()["detail"] == "Recurso no encontrado"
