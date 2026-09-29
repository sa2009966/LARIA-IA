"""Borrar mi cuenta borra todo lo mío, y nada de nadie más (ADR-019).

No existía: el único borrado era de administrador y solo desactivaba la cuenta.
Todo lo del estudiante —perfil, chats, documentos, originales, intentos— se
quedaba para siempre. Estos tests fijan qué significa "todo".
"""
from io import BytesIO
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from src.application.services.quiz_service import QuizService
from src.domain.value_objects.question import Difficulty, Quiz, QuizQuestion
from src.interfaces.api import dependencies as deps
from src.main import app
from tests.conftest import clear_dependency_caches

CLAVE = "SecurePass1x"


def _nivelacion(plan) -> Quiz:
    return Quiz(questions=[
        QuizQuestion(text=f"p{i} ⟨{'ABCD'[i % 4]}⟩", options={l: l for l in "ABCD"},
                     correct_answer="ABCD"[i % 4], difficulty=Difficulty.EASY,
                     concept_tags=(plan.topic,))
        for i in range(plan.total_items)
    ])


@pytest.fixture
def client():
    clear_dependency_caches()
    app.dependency_overrides.clear()
    ia = AsyncMock()
    ia.generate_diagnostic = AsyncMock(side_effect=_nivelacion)
    app.dependency_overrides[deps.get_quiz_service] = lambda: QuizService(
        document_repository=deps.get_document_repo(), quiz_repository=deps.get_quiz_repo(),
        attempt_repository=deps.get_attempt_repo(), interaction_repository=deps.get_interaction_repo(),
        ia_analyst=ia, event_bus=deps.get_event_bus(), profile_repository=deps.get_profile_repo(),
        session_repository=deps.get_session_repo(),
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    clear_dependency_caches()


def _alta(c: TestClient) -> tuple[dict, UUID]:
    s = uuid4().hex[:8]
    email = f"borrar_{s}@example.com"
    c.post("/api/v1/auth/register", json={"username": f"borrar_{s}", "email": email, "password": CLAVE})
    tok = c.post("/api/v1/auth/token", data={"username": email, "password": CLAVE}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    return h, UUID(c.get("/api/v1/users/me", headers=h).json()["id"])


def _llenar(c: TestClient, h: dict) -> None:
    """Un poco de todo: documento con original, chat, nivelación respondida."""
    doc = c.post("/api/v1/documents/upload", headers=h,
                 files={"file": ("apuntes.txt", BytesIO(b"Una variable es un valor."), "text/plain")},
                 data={"subject": "Matemática"}).json()["id"]
    chat = c.post("/api/v1/chats/", headers=h, json={"document_id": doc}).json()["id"]
    c.post(f"/api/v1/chats/{chat}/messages", headers=h, json={"role": "system", "content": "nota"})
    quiz = c.post("/api/v1/quizzes/diagnostic", headers=h, json={"topic": "historia"}).json()
    respuestas = {str(q["index"]): "A" for q in quiz["questions"]}
    c.post(f"/api/v1/quizzes/{quiz['id']}/attempts", headers=h, json={"answers": respuestas})


async def _huella(uid: UUID) -> dict:
    """Todo lo que el sistema guarda de una persona."""
    return {
        "usuario": await deps.get_user_repo().find_by_id(uid) is not None,
        "perfil": await deps.get_profile_repo().find_by_student(uid) is not None,
        "documentos": len(await deps.get_document_repo().find_by_owner(uid)),
        "chats": len(await deps.get_chat_repo().find_by_owner(uid)),
        "cuestionarios": len(await deps.get_quiz_repo().find_by_owner(uid)),
        "intentos": len(await deps.get_attempt_repo().find_by_student(uid)),
        "interacciones": len(await deps.get_interaction_repo().find_by_student(uid)),
    }


def _borrar(c, h, clave=CLAVE):
    return c.request("DELETE", "/api/v1/users/me", headers=h, json={"password": clave})


@pytest.mark.asyncio
async def test_borrar_mi_cuenta_no_deja_nada_mio(client: TestClient):
    h, uid = _alta(client)
    _llenar(client, h)
    antes = await _huella(uid)
    assert antes["documentos"] and antes["chats"] and antes["intentos"] and antes["perfil"]

    r = _borrar(client, h)

    assert r.status_code == 204, r.text
    assert await _huella(uid) == {
        "usuario": False, "perfil": False, "documentos": 0, "chats": 0,
        "cuestionarios": 0, "intentos": 0, "interacciones": 0,
    }


@pytest.mark.asyncio
async def test_no_toca_los_datos_de_otra_persona(client: TestClient):
    h_mia, _ = _alta(client)
    h_otra, uid_otra = _alta(client)
    _llenar(client, h_mia)
    _llenar(client, h_otra)
    antes = await _huella(uid_otra)

    _borrar(client, h_mia)

    assert await _huella(uid_otra) == antes


@pytest.mark.asyncio
async def test_con_la_contrasena_equivocada_no_se_borra_nada(client: TestClient):
    """Un token robado no debe bastar para destruir la cuenta de alguien."""
    h, uid = _alta(client)
    _llenar(client, h)
    antes = await _huella(uid)

    r = _borrar(client, h, clave="NoEsMiClave1x")

    assert r.status_code == 403
    assert await _huella(uid) == antes


def test_despues_el_token_ya_no_sirve(client: TestClient):
    h, _ = _alta(client)
    _borrar(client, h)

    assert client.get("/api/v1/users/me", headers=h).status_code == 401


def test_sin_token_no_se_puede_borrar_nada(client: TestClient):
    assert client.request("DELETE", "/api/v1/users/me", json={"password": CLAVE}).status_code == 401


def test_me_no_se_confunde_con_el_borrado_de_administrador(client: TestClient):
    """`/me` va antes que `/{user_id}`; al revés, "me" se leería como un id."""
    h, _ = _alta(client)

    r = _borrar(client, h)

    assert r.status_code == 204, "la ruta del administrador capturó /me"
