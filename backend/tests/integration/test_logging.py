"""Pruebas de integración: logging operativo de LARIA."""
from __future__ import annotations

import logging
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.domain.services.pedagogical_engine import PedagogicalEngine, TutorIntent
from src.infrastructure.logging_setup import configure_logging, reset_logging_for_tests
from src.interfaces.api import dependencies as deps
from src.main import app


def _clear_caches() -> None:
    for name in (
        "get_user_repo",
        "get_document_repo",
        "get_quiz_repo",
        "get_attempt_repo",
        "get_interaction_repo",
        "get_profile_repo",
        "get_session_repo",
        "get_ia_analyst",
        "get_event_bus",
        "get_metrics",
        "get_cache",
        "get_llm_gate",
        "get_model_router",
        "get_pedagogical_engine",
    ):
        fn = getattr(deps, name, None)
        if fn is not None and hasattr(fn, "cache_clear"):
            fn.cache_clear()


@pytest.fixture
def client():
    _clear_caches()
    reset_logging_for_tests()
    configure_logging(level="INFO", fmt="text")
    with TestClient(app) as c:
        yield c
    _clear_caches()


class TestLoggingIntegration:
    def test_configure_logging_attaches_root_handler(self):
        reset_logging_for_tests()
        assert len(logging.getLogger().handlers) == 0
        configure_logging(level="INFO", fmt="json")
        root = logging.getLogger()
        assert len(root.handlers) >= 1
        assert root.level == logging.INFO
        # idempotente
        configure_logging(level="DEBUG", fmt="text")
        assert len(root.handlers) == 1

    def test_health_emits_log_and_request_id(self, client: TestClient, caplog):
        """/health responde y propaga X-Request-Id; el cuerpo no loguea a INFO
        (el middleware degrada /health a DEBUG para no saturar probes)."""
        with caplog.at_level(logging.DEBUG, logger="laria.http"):
            r = client.get("/health")
        assert r.status_code == 200
        assert "X-Request-Id" in r.headers
        assert r.json().get("status") == "ok"
        assert any(
            "request method=GET" in rec.message and "path=/health" in rec.message
            for rec in caplog.records
        )

    def test_http_middleware_logs_api_request(self, client: TestClient, caplog):
        email = f"log_{uuid4().hex[:8]}@example.com"
        with caplog.at_level(logging.INFO, logger="laria.http"):
            r = client.post(
                "/api/v1/auth/register",
                json={
                    "username": f"log_{uuid4().hex[:6]}",
                    "email": email,
                    "password": "SecurePass1x",
                },
            )
        assert r.status_code == 201
        assert "X-Request-Id" in r.headers
        assert any(
            "request method=POST" in rec.message and "/api/v1/auth/register" in rec.message
            for rec in caplog.records
        )

    def test_pedagogical_engine_logs_decision(self, client: TestClient, caplog):
        with caplog.at_level(logging.INFO, logger="laria.pedagogy"):
            PedagogicalEngine().select(
                None, uuid4(), TutorIntent.ASK, ("integrales", "derivadas")
            )
        assert any("decision intent=ask" in rec.message for rec in caplog.records)

    def test_json_formatter_emits_parseable_line(self, capsys):
        reset_logging_for_tests()
        configure_logging(level="INFO", fmt="json")
        logging.getLogger("laria").info("json_probe_ok")
        out = capsys.readouterr().out
        assert "json_probe_ok" in out
        assert '"level": "INFO"' in out or '"level":"INFO"' in out
