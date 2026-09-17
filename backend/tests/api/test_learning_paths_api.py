"""Suite API: learning paths (rutas de aprendizaje).

La ruta es un plan: su progreso se proyecta desde la evidencia del perfil y no
se puede declarar por HTTP (ADR-008).
"""
import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from src.domain.aggregates.student_profile import StudentProfile
from src.interfaces.api import dependencies as deps
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


def _student_id(client, headers) -> UUID:
    return UUID(client.get("/api/v1/users/me", headers=headers).json()["id"])


def _con_mastery_medido(student_id: UUID, concepto: str, aciertos: int = 3) -> None:
    """Siembra evidencia calificada en el perfil, como lo haría un quiz."""
    profile = StudentProfile.create(student_id)
    for _ in range(aciertos):
        profile.record_concept_result(concepto, 1.0)
    asyncio.run(deps.get_profile_repo().save(profile))


def _sin_evidencia(student_id: UUID) -> None:
    """Vacía el mastery del perfil respetando el versionado optimista."""

    async def _run():
        repo = deps.get_profile_repo()
        profile = await repo.find_by_student(student_id) or StudentProfile.create(student_id)
        profile.mastery_by_concept.clear()
        await repo.save(profile)

    asyncio.run(_run())


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

    def test_el_cliente_no_puede_declarar_su_mastery(self, client):
        """El endpoint de escritura ya no existe (ADR-008).

        Permitía `PUT .../mastery: 0.9` y marcaba el módulo "completed": una
        segunda verdad del mastery, declarada por quien se evalúa, en un
        sistema cuyo principio es que responder bien no prueba comprensión.
        """
        headers = _setup(client)
        created = _create_path(client, headers).json()

        r = client.put(
            f"/api/v1/learning/paths/{created['id']}/modules/{created['modules'][0]['id']}/mastery",
            headers=headers,
            json={"mastery": 0.9},
        )
        assert r.status_code in (404, 405)

    def test_el_progreso_se_proyecta_desde_la_evidencia(self, client):
        headers = _setup(client)
        created = _create_path(client, headers).json()
        assert created["modules"][0]["mastery"] == 0.0
        assert created["modules"][1]["status"] == "locked"

        _con_mastery_medido(_student_id(client, headers), "grafos")

        body = client.get(
            f"/api/v1/learning/paths/{created['id']}", headers=headers
        ).json()

        assert body["modules"][0]["mastery"] > 0.7
        assert body["modules"][0]["status"] == "completed"
        # El módulo dependiente se abre por evidencia, no por declaración.
        assert body["modules"][1]["status"] == "available"
        assert body["progress"] == pytest.approx(0.5)

    def test_la_proyeccion_no_se_persiste_como_verdad(self, client):
        """Nadie guarda el progreso: se recalcula del perfil en cada lectura."""
        headers = _setup(client)
        created = _create_path(client, headers).json()
        student = _student_id(client, headers)
        _con_mastery_medido(student, "grafos")

        primera = client.get(
            f"/api/v1/learning/paths/{created['id']}", headers=headers
        ).json()
        assert primera["modules"][0]["status"] == "completed"

        # Se borra la evidencia: la ruta vuelve al estado que la evidencia dice.
        _sin_evidencia(student)

        segunda = client.get(
            f"/api/v1/learning/paths/{created['id']}", headers=headers
        ).json()
        assert segunda["modules"][0]["mastery"] == 0.0
        assert segunda["modules"][0]["status"] == "available"

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
