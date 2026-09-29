"""El lazo de evidencia del chat, de punta a punta (fase 2 del plan de corrección).

Recorre exactamente lo que debe hacer el frontend —chat vinculado al material,
turno de tutoría, quiz del chat, intento calificado en servidor— y comprueba lo
único que importa: que al final el **perfil del estudiante haya cambiado**.

Es el equivalente automático de `scripts/smoke_frontend_contract.py`, con IA
stub: si alguien vuelve a abrir el lazo, esto se pone en rojo.
"""
from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.application.services.analyze_document_service import AnalyzeDocumentService
from src.application.services.chat_tutor_service import ChatTutorService
from src.application.services.quiz_service import QuizService
from src.domain.value_objects.analysis_result import AnalysisResult
from src.domain.value_objects.question import Quiz, QuizQuestion
from src.interfaces.api import dependencies as deps
from src.main import app
from tests.conftest import clear_dependency_caches


def _stub_ia() -> AsyncMock:
    ia = AsyncMock()
    ia.analyze = AsyncMock(
        return_value=AnalysisResult(
            summary="Ecuaciones de primer grado",
            key_concepts=["variable", "ecuación"],
            suggested_questions=["¿Qué es una variable?"],
        )
    )
    ia.answer_question = AsyncMock(return_value="Restas 3 en ambos lados y divides entre 2.")
    ia.generate_quiz = AsyncMock(
        return_value=Quiz(
            questions=[
                QuizQuestion(
                    text="Si 2x + 3 = 7, ¿cuánto vale la variable x?",
                    options={"A": "2", "B": "5", "C": "7", "D": "1"},
                    correct_answer="A",
                )
            ]
        )
    )
    return ia


@pytest.fixture
def client():
    clear_dependency_caches()
    app.dependency_overrides.clear()
    ia = _stub_ia()

    def _analyze() -> AnalyzeDocumentService:
        return AnalyzeDocumentService(
            document_repository=deps.get_document_repo(),
            ia_analyst=ia,
            event_bus=deps.get_event_bus(),
            interaction_repository=deps.get_interaction_repo(),
            profile_repository=deps.get_profile_repo(),
            pedagogical_engine=deps.get_pedagogical_engine(),
            session_repository=deps.get_session_repo(),
        )

    def _quiz() -> QuizService:
        return QuizService(
            document_repository=deps.get_document_repo(),
            quiz_repository=deps.get_quiz_repo(),
            attempt_repository=deps.get_attempt_repo(),
            interaction_repository=deps.get_interaction_repo(),
            ia_analyst=ia,
            event_bus=deps.get_event_bus(),
            profile_repository=deps.get_profile_repo(),
            pedagogical_engine=deps.get_pedagogical_engine(),
            session_repository=deps.get_session_repo(),
        )

    def _tutor() -> ChatTutorService:
        # El servicio de chat construye su colaborador llamando a la función, no
        # por `Depends`, así que hay que sustituirlo aquí para que use el stub.
        return ChatTutorService(
            analyze_service=_analyze(),
            document_repository=deps.get_document_repo(),
            profile_repository=deps.get_profile_repo(),
        )

    app.dependency_overrides[deps.get_analyze_service] = _analyze
    app.dependency_overrides[deps.get_quiz_service] = _quiz
    app.dependency_overrides[deps.get_chat_tutor_service] = _tutor
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    clear_dependency_caches()


def _auth(client: TestClient) -> dict:
    sufijo = uuid4().hex[:8]
    email = f"loop_{sufijo}@example.com"
    r = client.post(
        "/api/v1/auth/register",
        json={"username": f"loop_{sufijo}", "email": email, "password": "SecurePass1x"},
    )
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/auth/token", data={"username": email, "password": "SecurePass1x"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_lo_que_hace_el_alumno_en_el_chat_llega_a_su_perfil(client: TestClient):
    headers = _auth(client)

    # 1. Material
    r = client.post(
        "/api/v1/documents/",
        headers=headers,
        json={
            "filename": "ecuaciones.txt",
            "content": "Una variable representa un valor desconocido. Una ecuación iguala dos expresiones.",
            "subject": "Matemática",
        },
    )
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]
    assert client.post(f"/api/v1/documents/{doc_id}/analyze", headers=headers).status_code == 200

    # 2. Chat vinculado al material: sin esto el motor pedagógico no entra
    r = client.post(
        "/api/v1/chats/", headers=headers, json={"title": "Dudas", "document_id": doc_id}
    )
    assert r.status_code == 201, r.text
    chat_id = r.json()["id"]

    # 3. Turno de tutoría: la respuesta la da el backend, con su envelope
    r = client.post(
        f"/api/v1/chats/{chat_id}/messages",
        headers=headers,
        json={"role": "user", "content": "¿cómo resuelvo 2x + 3 = 7?"},
    )
    assert r.status_code == 200, r.text
    asistente = [m for m in r.json()["messages"] if m["role"] == "assistant"]
    assert asistente, "el backend no respondió como tutor"
    envelope = asistente[-1]["metadata"]
    assert envelope["type"] in ("answer", "explanation", "hint", "quiz", "celebration")
    assert envelope["payload"]["grounded"] is True

    perfil_antes = client.get("/api/v1/learning/me/profile", headers=headers).json()

    # 4. Quiz del material del chat, sin respuestas correctas en la respuesta
    r = client.post(f"/api/v1/chats/{chat_id}/quiz?num_questions=1", headers=headers)
    assert r.status_code == 200, r.text
    quiz = r.json()
    assert "correct_answer" not in r.text

    # 5. Intento calificado en servidor
    r = client.post(
        f"/api/v1/quizzes/{quiz['id']}/attempts", headers=headers, json={"answers": {"0": "A"}}
    )
    assert r.status_code == 200, r.text
    intento = r.json()
    # El puntaje se cuenta en puntos, no en aciertos: acertar todo = total.
    assert intento["score"] == intento["total_points"]

    # 6. La evidencia llegó al perfil: esto es lo que el bypass del front rompía
    perfil = client.get("/api/v1/learning/me/profile", headers=headers).json()
    assert perfil["total_attempts"] > perfil_antes["total_attempts"]
    conceptos = {c["concept_key"]: c for c in perfil["mastery_by_concept"]}
    assert conceptos, "el intento no dejó evidencia por concepto"
    assert any(c["mastery"] > 0 for c in conceptos.values())


def test_un_chat_sin_material_no_puede_evaluar(client: TestClient):
    """La tutoría exige material; evaluar sin él sería corregir contra nada."""
    headers = _auth(client)
    r = client.post("/api/v1/chats/", headers=headers, json={"title": "Charla"})
    chat_id = r.json()["id"]

    r = client.post(f"/api/v1/chats/{chat_id}/quiz", headers=headers)

    assert r.status_code == 422
    assert "material" in r.json()["detail"].lower()
