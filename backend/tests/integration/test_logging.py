"""Pruebas de integración: logging operativo de LARIA."""
from __future__ import annotations

import logging
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.domain.services.pedagogical_engine import PedagogicalEngine, TutorIntent
from src.infrastructure.logging_setup import configure_logging, reset_logging_for_tests
from src.main import app
from tests.conftest import clear_dependency_caches


@pytest.fixture
def client():
    clear_dependency_caches()
    reset_logging_for_tests()
    configure_logging(level="INFO", fmt="text")
    with TestClient(app) as c:
        yield c
    clear_dependency_caches()


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

    def test_ready_no_spam_info(self, client: TestClient, caplog):
        """/ready es probe: DEBUG sí, INFO no. Sin cuerpos ni tokens."""
        with caplog.at_level(logging.INFO, logger="laria.http"):
            r = client.get("/ready")
        assert r.status_code == 200
        assert "X-Request-Id" in r.headers
        assert not any(
            "path=/ready" in rec.message for rec in caplog.records if rec.levelno >= logging.INFO
        )
        with caplog.at_level(logging.DEBUG, logger="laria.http"):
            r2 = client.get("/ready")
        assert r2.status_code == 200
        assert any(
            "request method=GET" in rec.message and "path=/ready" in rec.message
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
        joined = " ".join(rec.message for rec in caplog.records)
        assert "request method=POST" in joined
        assert "/api/v1/auth/register" in joined
        assert "SecurePass1x" not in joined
        assert "password" not in joined.lower()
        assert "Bearer " not in joined
        assert email not in joined

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

    def test_request_failed_logs_request_id_on_exception(self, caplog):
        from starlette.applications import Starlette
        from starlette.routing import Route

        from src.infrastructure.request_logging import RequestLoggingMiddleware

        async def boom(_request):
            raise RuntimeError("boom")

        mini = Starlette(routes=[Route("/boom", boom)])
        mini.add_middleware(RequestLoggingMiddleware)

        with caplog.at_level(logging.ERROR, logger="laria.http"):
            with TestClient(mini, raise_server_exceptions=False) as c:
                r = c.get("/boom", headers={"X-Request-Id": "trace-abc-123"})
        assert r.status_code == 500
        failed = [
            rec
            for rec in caplog.records
            if "request_failed" in rec.message and "trace-abc-123" in rec.message
        ]
        assert failed
        assert failed[0].levelno >= logging.ERROR
