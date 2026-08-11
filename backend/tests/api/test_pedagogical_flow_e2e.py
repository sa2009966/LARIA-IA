"""Smoke E2E pedagógico con IA stub (sin OpenAI real)."""
from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.application.services.analyze_document_service import AnalyzeDocumentService
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
            summary="Resumen de prueba",
            key_concepts=["fracción", "numerador"],
            suggested_questions=["¿Qué es una fracción?"],
        )
    )
    ia.answer_question = AsyncMock(return_value="Una fracción es parte de un todo.")
    ia.generate_quiz = AsyncMock(
        return_value=Quiz(
            questions=[
                QuizQuestion(
                    text="¿Cuál es el numerador en 3/4?",
                    options={"A": "3", "B": "4", "C": "7", "D": "1"},
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

    app.dependency_overrides[deps.get_analyze_service] = _analyze
    app.dependency_overrides[deps.get_quiz_service] = _quiz
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    clear_dependency_caches()


@pytest.mark.parametrize("run_id", [1, 2, 3])
def test_pedagogical_flow_register_to_profile(client: TestClient, run_id: int):
    email = f"e2e_{run_id}_{uuid4().hex[:8]}@example.com"
    user = f"e2e_{uuid4().hex[:6]}"
    assert client.post(
        "/api/v1/auth/register",
        json={"username": user, "email": email, "password": "SecurePass1x"},
    ).status_code == 201
    token = client.post(
        "/api/v1/auth/token",
        data={"username": email, "password": "SecurePass1x"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    up = client.post(
        "/api/v1/documents/",
        headers=headers,
        json={
            "filename": "fracciones.txt",
            "content": "Una fracción tiene numerador y denominador. 3/4 significa tres cuartos.",
            "subject": "Matemática",
        },
    )
    assert up.status_code == 201, up.text
    doc_id = up.json()["id"]

    an = client.post(f"/api/v1/documents/{doc_id}/analyze", headers=headers)
    assert an.status_code == 200, an.text

    ask = client.post(
        f"/api/v1/documents/{doc_id}/ask",
        headers=headers,
        json={"question": "no entiendo las fracciones"},
    )
    assert ask.status_code == 200, ask.text

    quiz = client.post(f"/api/v1/documents/{doc_id}/quiz?num_questions=1", headers=headers)
    assert quiz.status_code == 200, quiz.text
    quiz_id = quiz.json()["id"]

    attempt = client.post(
        f"/api/v1/quizzes/{quiz_id}/attempts",
        headers=headers,
        json={"answers": {"0": "A"}},
    )
    assert attempt.status_code == 200, attempt.text

    hist = client.get("/api/v1/learning/me", headers=headers)
    assert hist.status_code == 200
    assert len(hist.json()["attempts"]) >= 1

    profile = client.get("/api/v1/learning/me/profile", headers=headers)
    assert profile.status_code == 200, profile.text
    body = profile.json()
    assert body["total_attempts"] >= 1
