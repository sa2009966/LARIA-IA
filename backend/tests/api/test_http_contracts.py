"""Contratos HTTP: 422/409/404/502 alineados a la documentación."""
from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.application.services.analyze_document_service import AnalyzeDocumentService
from src.domain.ports.ia_analyst import IAAnalysisError
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
        # Cumple longitud del esquema pero falla política de dominio (sin dígito/mayúscula).
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
