"""Ramas restantes: readiness, config producción, quiz edges, embodiment timeout."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.infrastructure.config import Settings, validate_runtime_settings
from src.infrastructure.embodiment.stubs import NullSpeechToText
from src.infrastructure.metrics.in_memory_metrics import InMemoryMetrics


def _base(**kwargs) -> Settings:
    data = {
        "SECRET_KEY": "a" * 64,
        "OPENAI_API_KEY": "sk-test",
        "IA_PROVIDER": "openai",
        "APP_ENV": "production",
        "DB_PROVIDER": "mongodb",
        "MONGODB_URL": "mongodb://mongo:27017",
        "ENABLE_DOCS": False,
        "EVENT_BUS_BACKEND": "outbox",
        "RATE_LIMIT_BACKEND": "redis",
        "CACHE_BACKEND": "redis",
        "REDIS_URL": "redis://redis:6379/0",
        "RATE_LIMIT_ENABLED": True,
        "CORS_ORIGINS": ["https://laria.example"],
    }
    data.update(kwargs)
    return Settings(_env_file=None, **data)


def test_production_rejects_invalid_rate_limit_backend():
    with pytest.raises(RuntimeError, match="RATE_LIMIT_BACKEND"):
        validate_runtime_settings(_base(RATE_LIMIT_BACKEND="memcached"))


def test_production_rejects_invalid_event_bus_backend():
    with pytest.raises(RuntimeError, match="EVENT_BUS_BACKEND"):
        validate_runtime_settings(_base(EVENT_BUS_BACKEND="kafka"))


def test_production_rejects_invalid_cache_backend():
    with pytest.raises(RuntimeError, match="CACHE_BACKEND"):
        validate_runtime_settings(_base(CACHE_BACKEND="disk"))


def test_ready_mongodb_ping_error(monkeypatch):
    from src.infrastructure.config import settings
    from src.main import app

    monkeypatch.setattr(settings, "DB_PROVIDER", "mongodb")
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "memory")
    monkeypatch.setattr(settings, "CACHE_BACKEND", "memory")

    mock_db = MagicMock()
    mock_db.command = AsyncMock(side_effect=RuntimeError("mongo down"))
    with patch("src.infrastructure.mongodb.database.get_database", AsyncMock(return_value=mock_db)):
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/ready")
    assert r.status_code == 503
    assert "error" in r.json()["checks"]["mongodb"]


def test_ready_redis_ping_error(monkeypatch):
    from src.infrastructure.config import settings
    from src.main import app

    monkeypatch.setattr(settings, "DB_PROVIDER", "memory")
    monkeypatch.setattr(settings, "CACHE_BACKEND", "redis")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://localhost:6379/0")

    mock_redis = MagicMock()
    mock_redis.Redis.from_url.return_value.ping.side_effect = ConnectionError("redis down")
    with patch.dict("sys.modules", {"redis": mock_redis}):
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/ready")
    assert r.status_code == 503
    assert "error" in r.json()["checks"]["redis"]


@pytest.mark.asyncio
async def test_stt_timeout_records_device_error():
    metrics = InMemoryMetrics()

    class _SlowSTT(NullSpeechToText):
        async def _do_transcribe(self, audio_bytes: bytes) -> str:
            import asyncio

            await asyncio.sleep(1.0)
            return "late"

    text = await _SlowSTT(timeout_s=0.01, metrics=metrics).transcribe(b"wav")
    assert text == ""
    snap = metrics.snapshot()
    assert any("device_errors" in k for k in snap["counters"])


@pytest.mark.asyncio
async def test_quiz_service_missing_document_raises():
    from src.application.services.quiz_service import QuizService
    from src.infrastructure.persistence.in_memory_document_repo import InMemoryDocumentRepository
    from src.infrastructure.persistence.in_memory_quiz_attempt_repo import (
        InMemoryQuizAttemptRepository,
    )
    from src.infrastructure.persistence.in_memory_quiz_repo import InMemoryQuizRepository
    from src.infrastructure.persistence.in_memory_tutor_interaction_repo import (
        InMemoryTutorInteractionRepository,
    )

    svc = QuizService(
        document_repository=InMemoryDocumentRepository(),
        quiz_repository=InMemoryQuizRepository(),
        attempt_repository=InMemoryQuizAttemptRepository(),
        interaction_repository=InMemoryTutorInteractionRepository(),
        ia_analyst=MagicMock(),
    )
    with pytest.raises(ValueError, match="no encontrado|No encontrado|documento"):
        await svc.generate(uuid4(), user_id=uuid4(), num_questions=3)
