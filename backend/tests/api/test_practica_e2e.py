"""POST /quizzes/practice: practicar un tema sin material (no es nivelarse)."""
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from src.application.services.quiz_service import QuizService
from src.domain.value_objects.question import Quiz, QuizQuestion
from src.interfaces.api import dependencies as deps
from src.main import app
from tests.conftest import clear_dependency_caches

LETRAS = "ABCD"


def _desde_el_plan(plan) -> Quiz:
    preguntas, i = [], 0
    for peldano in plan.rungs:
        for n in range(peldano.items):
            c = LETRAS[i % 4]
            i += 1
            preguntas.append(QuizQuestion(
                text=f"[{peldano.difficulty.value}] #{i} ⟨{c}⟩", options={l: l for l in LETRAS},
                correct_answer=c, difficulty=peldano.difficulty,
                concept_tags=(peldano.concepts[n % len(peldano.concepts)],)))
    return Quiz(questions=preguntas)


@pytest.fixture
def client():
    clear_dependency_caches()
    app.dependency_overrides.clear()
    ia = AsyncMock()
    ia.generate_diagnostic = AsyncMock(side_effect=_desde_el_plan)
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


def _auth(c):
    s = uuid4().hex[:8]
    email = f"prac_{s}@example.com"
    c.post("/api/v1/auth/register", json={"username": f"prac_{s}", "email": email, "password": "SecurePass1x"})
    tok = c.post("/api/v1/auth/token", data={"username": email, "password": "SecurePass1x"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    return h, UUID(c.get("/api/v1/users/me", headers=h).json()["id"])


def _responder_bien(c, h, quiz):
    # Opciones barajadas en el servidor: se busca por el texto de la opción.
    r = {
        str(q["index"]): next(k for k, v in q["options"].items() if v == q["text"].rsplit("⟨", 1)[1].rstrip("⟩"))
        for q in quiz["questions"]
    }
    return c.post(f"/api/v1/quizzes/{quiz['id']}/attempts", headers=h, json={"answers": r}).json()


def test_genera_la_cantidad_pedida_sobre_el_tema(client):
    h, _ = _auth(client)

    r = client.post("/api/v1/quizzes/practice", headers=h, json={"topic": "fracciones", "num_questions": 7})

    assert r.status_code == 201, r.text
    q = r.json()
    assert len(q["questions"]) == 7
    assert q["document_id"] is None
    assert q["topic_label"] == "Fracciones"
    assert "correct_answer" not in r.text


@pytest.mark.asyncio
async def test_practicar_no_cambia_el_nivel_pero_si_deja_evidencia(client):
    """Practicar no es nivelarse: el veredicto solo lo da /diagnostic."""
    h, uid = _auth(client)
    quiz = client.post("/api/v1/quizzes/practice", headers=h, json={"topic": "fracciones"}).json()

    intento = _responder_bien(client, h, quiz)

    assert intento["placement"] is None
    perfil = await deps.get_profile_repo().find_by_student(uid)
    assert perfil.level_by_topic == {}, "la práctica escribió un nivel"
    assert perfil.mastery_by_concept, "la práctica no dejó evidencia"
    assert perfil.mastery_by_document == {}


def test_la_dificultad_sigue_al_nivel_que_ya_tiene(client):
    """Nivelado en intermedio, practica sobre todo en medio y algo de difícil."""
    h, _ = _auth(client)
    _responder_bien(client, h, client.post("/api/v1/quizzes/diagnostic", headers=h,
                                           json={"topic": "fracciones"}).json())

    q = client.post("/api/v1/quizzes/practice", headers=h, json={"topic": "fracciones"}).json()

    difs = [x["difficulty"] for x in q["questions"]]
    assert difs.count("medium") == 3 and difs.count("hard") == 1 and difs.count("easy") == 1


@pytest.mark.parametrize("n", [0, 21])
def test_fuera_de_rango_es_422(client, n):
    h, _ = _auth(client)

    r = client.post("/api/v1/quizzes/practice", headers=h, json={"topic": "fracciones", "num_questions": n})

    assert r.status_code == 422


def test_sin_sesion_es_401(client):
    assert client.post("/api/v1/quizzes/practice", json={"topic": "x y"}).status_code == 401
