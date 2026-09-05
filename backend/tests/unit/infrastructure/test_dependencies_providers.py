"""Cobertura de composición por provider en dependencies.py."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import clear_dependency_caches


@pytest.fixture(autouse=True)
def _clear_deps():
    clear_dependency_caches()
    yield
    clear_dependency_caches()


def test_mongodb_repositories_selected(monkeypatch):
    from src.infrastructure.config import settings
    from src.infrastructure.mongodb.user_repository import MongoDBUserRepository
    from src.infrastructure.mongodb.document_repository import MongoDBDocumentRepository
    from src.infrastructure.mongodb.quiz_repository import MongoDBQuizRepository
    from src.infrastructure.mongodb.gridfs_document_blob_store import GridFSDocumentBlobStore
    from src.interfaces.api import dependencies as deps

    monkeypatch.setattr(settings, "DB_PROVIDER", "mongodb")
    clear_dependency_caches()

    assert isinstance(deps.get_user_repo(), MongoDBUserRepository)
    assert isinstance(deps.get_document_blob_store(), GridFSDocumentBlobStore)
    assert isinstance(deps.get_document_repo(), MongoDBDocumentRepository)
    assert isinstance(deps.get_quiz_repo(), MongoDBQuizRepository)
    assert isinstance(deps.get_attempt_repo().__class__.__name__, str)
    assert isinstance(deps.get_interaction_repo().__class__.__name__, str)
    assert isinstance(deps.get_profile_repo().__class__.__name__, str)
    assert isinstance(deps.get_session_repo().__class__.__name__, str)


def test_redis_cache_selected(monkeypatch):
    from src.infrastructure.cache.cache_adapters import RedisCache
    from src.infrastructure.config import settings
    from src.interfaces.api import dependencies as deps

    monkeypatch.setattr(settings, "CACHE_BACKEND", "redis")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://localhost:6379/0")
    clear_dependency_caches()

    cache = deps.get_cache()
    assert isinstance(cache, RedisCache)


def test_outbox_event_bus_selected(monkeypatch):
    from src.infrastructure.config import settings
    from src.infrastructure.mongodb.outbox_event_bus import MongoOutboxEventBus
    from src.interfaces.api import dependencies as deps

    monkeypatch.setattr(settings, "DB_PROVIDER", "mongodb")
    monkeypatch.setattr(settings, "EVENT_BUS_BACKEND", "outbox")
    clear_dependency_caches()

    assert isinstance(deps.get_event_bus(), MongoOutboxEventBus)


def test_service_factories_wire_dependencies():
    from src.interfaces.api import dependencies as deps

    assert deps.get_user_service() is not None
    assert deps.get_document_service() is not None
    assert deps.get_analyze_service() is not None
    assert deps.get_quiz_service() is not None
    assert deps.get_learning_query_service() is not None
    assert deps.get_llm_gate() is not None
    assert deps.get_model_router() is not None
    assert deps.get_pedagogical_engine() is not None


def test_embodiment_providers_with_metrics():
    from src.interfaces.api import dependencies as deps

    assert deps.get_speech_to_text() is not None
    assert deps.get_text_to_speech() is not None
    assert deps.get_presence() is not None
    assert deps.get_device_command() is not None
    assert deps.get_sensor_input() is not None
    assert deps.get_affect_policy() is not None


def test_embodiment_providers_without_metrics(monkeypatch):
    from src.infrastructure.config import settings
    from src.interfaces.api import dependencies as deps

    monkeypatch.setattr(settings, "METRICS_ENABLED", False)
    clear_dependency_caches()
    assert deps.get_speech_to_text() is not None
    assert deps.get_device_command() is not None


@pytest.mark.asyncio
async def test_get_current_user_inactive_raises(monkeypatch):
    from uuid import uuid4

    import jwt
    from fastapi import HTTPException

    from src.domain.aggregates.user_aggregate import UserAggregate
    from src.infrastructure.config import JWT_ALGORITHM, settings
    from src.interfaces.api import dependencies as deps

    user = UserAggregate.register(f"u_{uuid4().hex[:6]}", f"{uuid4().hex[:8]}@t.local", "SecurePass1x!")
    user.deactivate()
    mock_repo = MagicMock()
    mock_repo.find_by_id = AsyncMock(return_value=user)
    token = jwt.encode({"sub": str(user.id)}, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)

    with patch.object(deps, "get_user_repo", return_value=mock_repo):
        with pytest.raises(HTTPException) as exc:
            await deps.get_current_user(token)
    assert exc.value.status_code == 401
    assert "inactivo" in exc.value.detail.lower()
