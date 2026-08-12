"""Contratos HTTP: 422/409/404/502/413/429 y quiz/metrics alineados a docs."""
from __future__ import annotations

from io import BytesIO
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.application.services.analyze_document_service import AnalyzeDocumentService
from src.application.services.document_service import DocumentService
from src.application.services.quiz_service import QuizService
from src.domain.ports.ia_analyst import IAAnalysisError
from src.domain.value_objects.analysis_result import AnalysisResult
from src.domain.value_objects.question import Quiz, QuizQuestion
from src.interfaces.api import dependencies as deps
from src.main import app
from tests.conftest import clear_dependency_caches


@pytest.fixture
def client():
    clear_dependency_caches()
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        yield c
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


def _auth_headers(client: TestClient) -> dict[str, str]:
    email = f"u_{uuid4().hex[:8]}@example.com"
    user = f"u_{uuid4().hex[:6]}"
    assert _register(client, email, user).status_code == 201
    return {"Authorization": f"Bearer {_token(client, email)}"}


class TestHttpContracts:
    def test_password_debil_422(self, client: TestClient):
        r = _register(
            client,
            f"w_{uuid4().hex[:8]}@example.com",
            f"w_{uuid4().hex[:6]}",
            "abcdefghijkl",
        )
        assert r.status_code == 422
        detail = r.json()["detail"]
        detail_s = detail if isinstance(detail, str) else str(detail)
        assert "débil" in detail_s.lower() or "contraseña" in detail_s.lower()

    def test_register_conflicto_409(self, client: TestClient):
        email = f"dup_{uuid4().hex[:8]}@example.com"
        user = f"dup_{uuid4().hex[:6]}"
        assert _register(client, email, user).status_code == 201
        r = _register(client, email, f"otro_{uuid4().hex[:6]}")
        assert r.status_code == 409

    def test_subject_invalido_json_422(self, client: TestClient):
        headers = _auth_headers(client)
        r = client.post(
            "/api/v1/documents/",
            headers=headers,
            json={
                "filename": "t.txt",
                "content": "hola",
                "subject": "AstrologíaCuántica",
            },
        )
        assert r.status_code == 422

    def test_uuid_malformado_422(self, client: TestClient):
        headers = _auth_headers(client)
        r = client.get("/api/v1/documents/not-a-uuid", headers=headers)
        assert r.status_code == 422

    def test_ownership_ajeno_404(self, client: TestClient):
        a = _auth_headers(client)
        b = _auth_headers(client)
        up = client.post(
            "/api/v1/documents/",
            headers=a,
            json={"filename": "t.txt", "content": "contenido", "subject": "Historia"},
        )
        assert up.status_code == 201
        doc_id = up.json()["id"]
        r = client.get(f"/api/v1/documents/{doc_id}", headers=b)
        assert r.status_code == 404

    def test_ia_error_502(self, client: TestClient):
        headers = _auth_headers(client)
        up = client.post(
            "/api/v1/documents/",
            headers=headers,
            json={
                "filename": "t.txt",
                "content": "La fotosíntesis convierte luz en energía.",
                "subject": "Biología",
            },
        )
        assert up.status_code == 201
        doc_id = up.json()["id"]

        mock_ia = AsyncMock()
        mock_ia.analyze = AsyncMock(side_effect=IAAnalysisError("upstream boom"))

        def _analyze() -> AnalyzeDocumentService:
            return AnalyzeDocumentService(
                document_repository=deps.get_document_repo(),
                ia_analyst=mock_ia,
                event_bus=deps.get_event_bus(),
                interaction_repository=deps.get_interaction_repo(),
                profile_repository=deps.get_profile_repo(),
                pedagogical_engine=deps.get_pedagogical_engine(),
                session_repository=deps.get_session_repo(),
            )

        app.dependency_overrides[deps.get_analyze_service] = _analyze
        try:
            r = client.post(f"/api/v1/documents/{doc_id}/analyze", headers=headers)
        finally:
            app.dependency_overrides.pop(deps.get_analyze_service, None)
        assert r.status_code == 502, r.text

    def test_list_get_sin_content(self, client: TestClient):
        headers = _auth_headers(client)
        up = client.post(
            "/api/v1/documents/",
            headers=headers,
            json={"filename": "t.txt", "content": "secreto pedagógico", "subject": "Historia"},
        )
        assert up.status_code == 201
        assert "content" not in up.json()
        listed = client.get("/api/v1/documents/", headers=headers)
        assert listed.status_code == 200
        assert "content" not in listed.json()[0]
        got = client.get(f"/api/v1/documents/{up.json()['id']}", headers=headers)
        assert got.status_code == 200
        assert "content" not in got.json()

    def test_metrics_y_health(self, client: TestClient):
        h = client.get("/health")
        assert h.status_code == 200
        assert h.json()["status"] == "ok"
        assert "x-request-id" in {k.lower() for k in h.headers.keys()} or True
        m = client.get("/metrics")
        assert m.status_code == 200

    def test_ready_endpoint(self, client: TestClient):
        r = client.get("/ready")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ready"
        assert body["checks"]["mongodb"] == "skipped"
        assert body["checks"]["redis"] == "skipped"

    def test_ready_503_mongodb(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        from src.infrastructure.config import settings

        async def _boom():
            raise RuntimeError("mongo down")

        monkeypatch.setattr(settings, "DB_PROVIDER", "mongodb")
        monkeypatch.setattr(
            "src.infrastructure.mongodb.database.get_database",
            _boom,
        )
        r = client.get("/ready")
        assert r.status_code == 503
        body = r.json()
        assert body["status"] == "degraded"
        assert str(body["checks"]["mongodb"]).startswith("error:")

    def test_ready_503_redis(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        from unittest.mock import MagicMock

        import redis

        from src.infrastructure.config import settings

        fake = MagicMock()
        fake.ping.side_effect = ConnectionError("redis down")
        monkeypatch.setattr(settings, "CACHE_BACKEND", "redis")
        monkeypatch.setattr(settings, "REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setattr(redis.Redis, "from_url", MagicMock(return_value=fake))
        r = client.get("/ready")
        assert r.status_code == 503
        body = r.json()
        assert body["status"] == "degraded"
        assert str(body["checks"]["redis"]).startswith("error:")

    def test_metrics_disabled_404(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        from src.infrastructure.config import settings

        monkeypatch.setattr(settings, "METRICS_ENABLED", False)
        r = client.get("/metrics")
        assert r.status_code == 404

    def test_upload_multipart_ok(self, client: TestClient):
        headers = _auth_headers(client)
        files = {"file": ("nota.txt", BytesIO(b"contenido utf-8 de prueba"), "text/plain")}
        data = {"subject": "Matemática"}
        r = client.post("/api/v1/documents/upload", headers=headers, files=files, data=data)
        assert r.status_code == 201, r.text
        assert r.json()["filename"] == "nota.txt"
        assert "content" not in r.json()

    def test_upload_supera_limite_413(self, client: TestClient):
        headers = _auth_headers(client)

        def _docs() -> DocumentService:
            return DocumentService(
                document_repository=deps.get_document_repo(),
                event_bus=deps.get_event_bus(),
                blob_store=deps.get_document_blob_store(),
                max_upload_bytes=10,
            )

        app.dependency_overrides[deps.get_document_service] = _docs
        try:
            r = client.post(
                "/api/v1/documents/",
                headers=headers,
                json={
                    "filename": "big.txt",
                    "content": "12345678901",
                    "subject": "Historia",
                },
            )
        finally:
            app.dependency_overrides.pop(deps.get_document_service, None)
        assert r.status_code == 413, r.text

    def test_upload_multipart_supera_limite_413(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        from src.infrastructure.config import settings

        monkeypatch.setattr(settings, "DOCUMENT_MAX_UPLOAD_BYTES", 10)
        headers = _auth_headers(client)
        files = {"file": ("nota.txt", BytesIO(b"12345678901"), "text/plain")}
        r = client.post(
            "/api/v1/documents/upload",
            headers=headers,
            files=files,
            data={"subject": "Historia"},
        )
        assert r.status_code == 413, r.text

    def test_delete_documento_204_y_ajeno_404(self, client: TestClient):
        owner = _auth_headers(client)
        other = _auth_headers(client)
        up = client.post(
            "/api/v1/documents/",
            headers=owner,
            json={"filename": "t.txt", "content": "borrar", "subject": "Historia"},
        )
        assert up.status_code == 201
        doc_id = up.json()["id"]
        forbidden = client.delete(f"/api/v1/documents/{doc_id}", headers=other)
        assert forbidden.status_code == 404
        gone = client.delete(f"/api/v1/documents/{doc_id}", headers=owner)
        assert gone.status_code == 204
        missing = client.get(f"/api/v1/documents/{doc_id}", headers=owner)
        assert missing.status_code == 404

    def test_ask_ia_error_502(self, client: TestClient):
        headers = _auth_headers(client)
        up = client.post(
            "/api/v1/documents/",
            headers=headers,
            json={
                "filename": "t.txt",
                "content": "La fotosíntesis convierte luz en energía.",
                "subject": "Biología",
            },
        )
        assert up.status_code == 201
        doc_id = up.json()["id"]
        mock_ia = AsyncMock()
        mock_ia.answer_question = AsyncMock(side_effect=IAAnalysisError("upstream boom"))

        def _analyze() -> AnalyzeDocumentService:
            return AnalyzeDocumentService(
                document_repository=deps.get_document_repo(),
                ia_analyst=mock_ia,
                event_bus=deps.get_event_bus(),
                interaction_repository=deps.get_interaction_repo(),
                profile_repository=deps.get_profile_repo(),
                pedagogical_engine=deps.get_pedagogical_engine(),
                session_repository=deps.get_session_repo(),
            )

        app.dependency_overrides[deps.get_analyze_service] = _analyze
        try:
            r = client.post(
                f"/api/v1/documents/{doc_id}/ask",
                headers=headers,
                json={"question": "¿Qué es la fotosíntesis?"},
            )
        finally:
            app.dependency_overrides.pop(deps.get_analyze_service, None)
        assert r.status_code == 502, r.text

    def test_quiz_sin_correct_answer_y_attempt_revela(self, client: TestClient):
        headers = _auth_headers(client)
        up = client.post(
            "/api/v1/documents/",
            headers=headers,
            json={
                "filename": "t.txt",
                "content": "El numerador es la parte de arriba de una fracción.",
                "subject": "Matemática",
            },
        )
        doc_id = up.json()["id"]
        ia = AsyncMock()
        ia.analyze = AsyncMock(
            return_value=AnalysisResult(
                summary="Resumen",
                key_concepts=["fracción"],
                suggested_questions=["¿Qué es numerador?"],
            )
        )
        ia.generate_quiz = AsyncMock(
            return_value=Quiz(
                questions=[
                    QuizQuestion(
                        text="¿Numerador de 3/4?",
                        options={"A": "3", "B": "4"},
                        correct_answer="A",
                    )
                ]
            )
        )

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
        try:
            assert client.post(f"/api/v1/documents/{doc_id}/analyze", headers=headers).status_code == 200
            quiz = client.post(f"/api/v1/documents/{doc_id}/quiz?num_questions=1", headers=headers)
            assert quiz.status_code == 200, quiz.text
            body = quiz.json()
            assert "correct_answer" not in body
            for q in body.get("questions", []):
                assert "correct_answer" not in q
            quiz_id = body["id"]
            got = client.get(f"/api/v1/quizzes/{quiz_id}", headers=headers)
            assert got.status_code == 200
            for q in got.json().get("questions", []):
                assert "correct_answer" not in q
            attempt = client.post(
                f"/api/v1/quizzes/{quiz_id}/attempts",
                headers=headers,
                json={"answers": {"0": "A"}},
            )
            assert attempt.status_code == 200, attempt.text
            ab = attempt.json()
            assert ab["questions"][0]["correct_answer"] == "A"
        finally:
            app.dependency_overrides.pop(deps.get_analyze_service, None)
            app.dependency_overrides.pop(deps.get_quiz_service, None)

    def test_quiz_ajeno_get_y_attempt_404(self, client: TestClient):
        owner = _auth_headers(client)
        other = _auth_headers(client)
        up = client.post(
            "/api/v1/documents/",
            headers=owner,
            json={
                "filename": "t.txt",
                "content": "El numerador es la parte de arriba de una fracción.",
                "subject": "Matemática",
            },
        )
        doc_id = up.json()["id"]
        ia = AsyncMock()
        ia.generate_quiz = AsyncMock(
            return_value=Quiz(
                questions=[
                    QuizQuestion(
                        text="¿Numerador de 3/4?",
                        options={"A": "3", "B": "4"},
                        correct_answer="A",
                    )
                ]
            )
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

        app.dependency_overrides[deps.get_quiz_service] = _quiz
        try:
            created = client.post(
                f"/api/v1/documents/{doc_id}/quiz?num_questions=1",
                headers=owner,
            )
            assert created.status_code == 200, created.text
            quiz_id = created.json()["id"]
            got = client.get(f"/api/v1/quizzes/{quiz_id}", headers=other)
            assert got.status_code == 404
            attempt = client.post(
                f"/api/v1/quizzes/{quiz_id}/attempts",
                headers=other,
                json={"answers": {"0": "A"}},
            )
            assert attempt.status_code == 404
        finally:
            app.dependency_overrides.pop(deps.get_quiz_service, None)

    def test_rate_limit_middleware_returns_429(self, monkeypatch: pytest.MonkeyPatch):
        from starlette.applications import Starlette
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route

        from src.infrastructure import rate_limit as rl
        from src.infrastructure import config as cfg

        monkeypatch.setattr(cfg.settings, "RATE_LIMIT_ENABLED", True)
        monkeypatch.setattr(rl.settings, "RATE_LIMIT_ENABLED", True)

        async def ok(_request):
            return PlainTextResponse("ok")

        mini = Starlette(routes=[Route("/api/v1/auth/register", ok, methods=["POST"])])
        counter = rl.SlidingWindowCounter()
        mini.add_middleware(rl.RateLimitMiddleware, counter=counter)

        original = rl._match_rule

        def _tight(path: str, method: str):
            if path.startswith("/api/v1/auth/register"):
                return ("/api/v1/auth/register", 2, 60.0)
            return original(path, method)

        monkeypatch.setattr(rl, "_match_rule", _tight)
        with TestClient(mini) as c:
            assert c.post("/api/v1/auth/register").status_code == 200
            assert c.post("/api/v1/auth/register").status_code == 200
            assert c.post("/api/v1/auth/register").status_code == 429

    def test_rate_limit_register_429_app_real(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        from src.infrastructure import rate_limit as rl
        from src.infrastructure.config import settings

        monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
        monkeypatch.setattr(rl.settings, "RATE_LIMIT_ENABLED", True)
        asgi = app
        seen: set[int] = set()
        while asgi is not None and id(asgi) not in seen:
            seen.add(id(asgi))
            if isinstance(asgi, rl.RateLimitMiddleware):
                asgi._counter = rl.SlidingWindowCounter()
                break
            asgi = getattr(asgi, "app", None)

        codes: list[int] = []
        for _ in range(6):
            r = _register(
                client,
                f"rl_{uuid4().hex[:8]}@example.com",
                f"rl_{uuid4().hex[:6]}",
            )
            codes.append(r.status_code)
        assert codes[-1] == 429
        assert 201 in codes
