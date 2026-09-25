""""Quiero aprender X": nivelación por rondas, de punta a punta (ADR-016, ADR-017).

El flujo que se pidió, literal:

    el estudiante dice "quiero aprender ecuaciones"
    → ronda base, preguntas básicas
    → si la pasa, se guarda que ya no está en lo básico y se ofrece otra ronda
    → ronda avanzada, preguntas más duras
    → si la pasa, se guarda que está en avanzado

Sin material. Lo que se comprueba es lo que no se ve en un test de unidad: que
el backend sepa en qué ronda vas sin que el cliente lleve estado, que el nivel
quede guardado en el perfil, y que la evidencia no invente un documento.
"""
from __future__ import annotations

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


def _generar_desde_el_plan(plan) -> Quiz:
    """Un modelo obediente: devuelve exactamente la escalera que el dominio pidió.

    Se construye desde el plan recibido para que el test pruebe el reparto real
    de cada ronda, no uno escrito a mano que podría desincronizarse.

    La correcta **rota entre A, B, C y D**. Con todas en "A", `ensure_quiz_quality`
    detecta el sesgo y reequilibra las claves —con razón: si no, se aprobaría
    marcando siempre lo mismo— y el test ya no sabría cuál es la buena. La letra
    viaja en el enunciado para que el test pueda simular a quien sabe la respuesta.
    """
    preguntas = []
    i = 0
    for peldano in plan.rungs:
        for n in range(peldano.items):
            concepto = peldano.concepts[n % len(peldano.concepts)]
            correcta = LETRAS[i % 4]
            i += 1
            preguntas.append(
                QuizQuestion(
                    text=f"[{peldano.difficulty.value}] {concepto} #{n} ⟨{correcta}⟩",
                    options={letra: f"opción {letra}" for letra in LETRAS},
                    correct_answer=correcta,
                    difficulty=peldano.difficulty,
                    concept_tags=(concepto,),
                )
            )
    return Quiz(questions=preguntas)


def _correcta(pregunta: dict) -> str:
    return pregunta["text"].rsplit("⟨", 1)[1].rstrip("⟩")


def _incorrecta(pregunta: dict) -> str:
    return next(l for l in LETRAS if l != _correcta(pregunta))


@pytest.fixture
def client():
    clear_dependency_caches()
    app.dependency_overrides.clear()
    ia = AsyncMock()
    ia.generate_diagnostic = AsyncMock(side_effect=_generar_desde_el_plan)

    def _quiz() -> QuizService:
        return QuizService(
            document_repository=deps.get_document_repo(),
            quiz_repository=deps.get_quiz_repo(),
            attempt_repository=deps.get_attempt_repo(),
            interaction_repository=deps.get_interaction_repo(),
            ia_analyst=ia,
            event_bus=deps.get_event_bus(),
            profile_repository=deps.get_profile_repo(),
            # Con sesiones: es lo que tiene producción, y lo que rompía cuando
            # un quiz sin documento buscaba la sesión de `None`.
            session_repository=deps.get_session_repo(),
        )

    app.dependency_overrides[deps.get_quiz_service] = _quiz
    with TestClient(app) as c:
        c.ia = ia
        yield c
    app.dependency_overrides.clear()
    clear_dependency_caches()


def _auth(client: TestClient) -> tuple[dict, str]:
    sufijo = uuid4().hex[:8]
    email = f"niv_{sufijo}@example.com"
    r = client.post(
        "/api/v1/auth/register",
        json={"username": f"niv_{sufijo}", "email": email, "password": "SecurePass1x"},
    )
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/auth/token", data={"username": email, "password": "SecurePass1x"})
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return headers, client.get("/api/v1/users/me", headers=headers).json()["id"]


def _pedir(client, headers, tema="ecuaciones") -> dict:
    r = client.post("/api/v1/quizzes/diagnostic", headers=headers, json={"topic": tema})
    assert r.status_code == 201, r.text
    return r.json()


def _responder(client, headers, quiz: dict, acierta) -> dict:
    """`acierta(pregunta) -> bool` decide qué ítems se contestan bien."""
    respuestas = {
        str(q["index"]): (_correcta(q) if acierta(q) else _incorrecta(q))
        for q in quiz["questions"]
    }
    r = client.post(
        f"/api/v1/quizzes/{quiz['id']}/attempts", headers=headers, json={"answers": respuestas}
    )
    assert r.status_code == 200, r.text
    return r.json()


def todas(_q) -> bool:
    return True


def ninguna(_q) -> bool:
    return False


# --- La primera ronda ----------------------------------------------------------------


def test_un_tema_basta_y_empieza_por_lo_basico(client: TestClient):
    headers, _ = _auth(client)

    quiz = _pedir(client, headers)

    assert quiz["document_id"] is None, "no hace falta material"
    assert quiz["topic"] == "ecuaciones lineales"
    difs = [q["difficulty"] for q in quiz["questions"]]
    assert len(difs) == 6
    assert difs.count("easy") == 4 and difs.count("medium") == 2
    assert "hard" not in difs, "no se asume que sabe: la primera ronda no es difícil"


def test_el_cliente_nunca_ve_la_respuesta_correcta(client: TestClient):
    headers, _ = _auth(client)

    r = client.post("/api/v1/quizzes/diagnostic", headers=headers, json={"topic": "ecuaciones"})

    assert "correct_answer" not in r.text


# --- El flujo completo ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_aprobar_las_dos_rondas_deja_al_estudiante_en_avanzado(client: TestClient):
    """El flujo que se pidió, de principio a fin."""
    headers, student_id = _auth(client)

    # Ronda 1: lo básico. La aprueba.
    base = _pedir(client, headers)
    r1 = _responder(client, headers, base, todas)
    assert r1["placement"] == {
        "topic": "ecuaciones lineales",
        "round": "base",
        "level": "intermedio",
        "passed": True,
        "has_next_round": True,
    }

    # Pide lo mismo: el backend sabe que ya superó lo básico.
    avanzada = _pedir(client, headers)
    difs = [q["difficulty"] for q in avanzada["questions"]]
    assert len(difs) == 8
    assert "easy" not in difs, "lo básico ya se demostró"
    assert difs.count("hard") == 5

    # Ronda 2: la aprueba.
    r2 = _responder(client, headers, avanzada, todas)
    assert r2["placement"]["level"] == "avanzado"
    assert r2["placement"]["has_next_round"] is False

    # Y queda guardado en el perfil, que es lo que usará la ruta de aprendizaje.
    perfil = await deps.get_profile_repo().find_by_student(UUID(student_id))
    assert perfil.level_for_topic("ecuaciones lineales") == "avanzado"


@pytest.mark.asyncio
async def test_suspender_lo_basico_deja_en_basico_y_no_ofrece_mas(client: TestClient):
    headers, student_id = _auth(client)

    r = _responder(client, headers, _pedir(client, headers), ninguna)

    assert r["placement"]["level"] == "basico"
    assert r["placement"]["passed"] is False
    assert r["placement"]["has_next_round"] is False
    perfil = await deps.get_profile_repo().find_by_student(UUID(student_id))
    assert perfil.level_for_topic("ecuaciones lineales") == "basico"


def test_suspender_la_avanzada_no_ofrece_repetirla_en_bucle(client: TestClient):
    headers, _ = _auth(client)
    _responder(client, headers, _pedir(client, headers), todas)

    r = _responder(client, headers, _pedir(client, headers), ninguna)

    assert r["placement"]["level"] == "intermedio"
    assert r["placement"]["has_next_round"] is False


def test_el_nivel_se_reconoce_lo_escriba_como_lo_escriba(client: TestClient):
    """El bug que casi se cuela, y era invisible: nada fallaba, no se avanzaba.

    El nivel se guarda bajo el tema canónico ("ecuaciones lineales") y el alumno
    escribe lo que quiere ("ecuaciones"). Buscándolo por lo escrito no aparecía
    nunca, y el estudiante recibía la ronda básica una y otra vez.
    """
    headers, _ = _auth(client)
    _responder(client, headers, _pedir(client, headers, tema="ecuaciones"), todas)

    # Mismo tema, escrito de otra forma: tiene que saber que ya superó lo básico.
    siguiente = _pedir(client, headers, tema="Ecuaciones Lineales")

    assert len(siguiente["questions"]) == 8, "no reconoció el nivel ya alcanzado"


# --- Lo que no debe ensuciarse -------------------------------------------------------


@pytest.mark.asyncio
async def test_la_nivelacion_no_inventa_un_documento(client: TestClient):
    """Un id sintético acabaría en las recomendaciones apuntando a nada."""
    headers, student_id = _auth(client)

    _responder(client, headers, _pedir(client, headers), todas)

    perfil = await deps.get_profile_repo().find_by_student(UUID(student_id))
    assert perfil.mastery_by_concept, "no aterrizó evidencia en ningún concepto"
    assert perfil.mastery_by_document == {}


def test_el_historial_no_manda_la_cadena_none(client: TestClient):
    """`str(None)` es "None": el cliente habría recibido un id que no existe."""
    headers, _ = _auth(client)
    _responder(client, headers, _pedir(client, headers), todas)

    historial = client.get("/api/v1/learning/me", headers=headers).json()

    assert historial["attempts"], "el intento no aparece en el historial"
    assert historial["attempts"][0]["document_id"] is None
    assert '"None"' not in client.get("/api/v1/learning/me", headers=headers).text


def test_un_quiz_sobre_material_no_trae_veredicto(client: TestClient):
    """`placement` solo existe en nivelación: no se le cuela a los quizzes normales."""
    headers, _ = _auth(client)
    quiz = _pedir(client, headers)

    r = _responder(client, headers, quiz, todas)

    assert r["placement"] is not None  # este sí es de nivelación
    # El contrato lo declara opcional para el resto de quizzes.
    from src.interfaces.schemas.quiz_schemas import QuizAttemptResponse

    assert QuizAttemptResponse.model_fields["placement"].default is None


# --- Errores -------------------------------------------------------------------------


def test_un_tema_vacio_no_llega_al_modelo(client: TestClient):
    headers, _ = _auth(client)

    r = client.post("/api/v1/quizzes/diagnostic", headers=headers, json={"topic": "  "})

    assert r.status_code == 422
    client.ia.generate_diagnostic.assert_not_awaited()


def test_hace_falta_estar_autenticado(client: TestClient):
    assert client.post("/api/v1/quizzes/diagnostic", json={"topic": "x"}).status_code == 401
