"""Suite API: learning paths (rutas de aprendizaje)."""
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


def _setup(client):
    email = f"lp_{uuid4().hex[:8]}@example.com"
    username = f"lp_{uuid4().hex[:6]}"
    r = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": "SecurePass1x"},
    )
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/auth/token", data={"username": email, "password": "SecurePass1x"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_path(client, headers):
    return client.post(
        "/api/v1/learning/paths",
        headers=headers,
        json={
            "subject": "Matemática",
            "title": "Grafos",
            "modules": [
                {"concept": "grafos", "difficulty": "easy"},
                {"concept": "bfs", "prerequisites": ["grafos"], "difficulty": "medium"},
            ],
        },
    )


class TestLearningPathsAPI:

    def test_create_path(self, client):
        headers = _setup(client)
        r = _create_path(client, headers)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["subject"] == "Matemática"
        assert body["progress"] == 0.0
        assert len(body["modules"]) == 2
        assert body["modules"][0]["status"] == "available"
        assert body["modules"][1]["status"] == "locked"

    def test_list_paths(self, client):
        headers = _setup(client)
        _create_path(client, headers)
        _create_path(client, headers)

        r = client.get("/api/v1/learning/paths", headers=headers)
        assert r.status_code == 200
        assert len(r.json()["paths"]) == 2

    def test_get_path(self, client):
        headers = _setup(client)
        created = _create_path(client, headers).json()

        r = client.get(f"/api/v1/learning/paths/{created['id']}", headers=headers)
        assert r.status_code == 200
        assert r.json()["title"] == "Grafos"

    def test_get_path_ownership_404(self, client):
        headers_a = _setup(client)
        headers_b = _setup(client)
        created = _create_path(client, headers_a).json()

        r = client.get(f"/api/v1/learning/paths/{created['id']}", headers=headers_b)
        assert r.status_code == 404

    def test_get_path_not_found(self, client):
        headers = _setup(client)
        r = client.get(f"/api/v1/learning/paths/{uuid4()}", headers=headers)
        assert r.status_code == 404

    def test_update_module_mastery_unlocks(self, client):
        headers = _setup(client)
        created = _create_path(client, headers).json()
        path_id = created["id"]
        first_module = created["modules"][0]

        r = client.put(
            f"/api/v1/learning/paths/{path_id}/modules/{first_module['id']}/mastery",
            headers=headers,
            json={"mastery": 0.9},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["modules"][0]["status"] == "completed"
        assert body["modules"][1]["status"] == "available"
        assert body["progress"] == pytest.approx(0.5)

    def test_update_module_mastery_ownership_404(self, client):
        headers_a = _setup(client)
        headers_b = _setup(client)
        created = _create_path(client, headers_a).json()

        r = client.put(
            f"/api/v1/learning/paths/{created['id']}/modules/{created['modules'][0]['id']}/mastery",
            headers=headers_b,
            json={"mastery": 0.9},
        )
        assert r.status_code == 404

    def test_update_module_invalid_mastery_422(self, client):
        headers = _setup(client)
        created = _create_path(client, headers).json()
        first = created["modules"][0]

        r = client.put(
            f"/api/v1/learning/paths/{created['id']}/modules/{first['id']}/mastery",
            headers=headers,
            json={"mastery": 1.5},
        )
        assert r.status_code == 422

    def test_delete_path(self, client):
        headers = _setup(client)
        created = _create_path(client, headers).json()

        r = client.delete(f"/api/v1/learning/paths/{created['id']}", headers=headers)
        assert r.status_code == 204

        r = client.get(f"/api/v1/learning/paths/{created['id']}", headers=headers)
        assert r.status_code == 404

    def test_delete_path_ownership_404(self, client):
        headers_a = _setup(client)
        headers_b = _setup(client)
        created = _create_path(client, headers_a).json()

        r = client.delete(f"/api/v1/learning/paths/{created['id']}", headers=headers_b)
        assert r.status_code == 404

    def test_server_routes_conflict_with_history(self, client):
        # /learning/paths no debe interferir con /learning/me
        headers = _setup(client)
        r = client.get("/api/v1/learning/me", headers=headers)
        assert r.status_code == 200
