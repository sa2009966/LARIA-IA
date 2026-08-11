"""Fail-fast de producción vs demo."""
import pytest

from src.infrastructure.config import Settings, validate_runtime_settings


def _base(**kwargs) -> Settings:
    data = {
        "SECRET_KEY": "a" * 64,
        "OPENAI_API_KEY": "sk-test",
        "IA_PROVIDER": "openai",
        "APP_ENV": "development",
        "DB_PROVIDER": "memory",
        "ENABLE_DOCS": True,
        "EVENT_BUS_BACKEND": "memory",
    }
    data.update(kwargs)
    return Settings(**data)


def test_development_allows_memory_and_docs():
    validate_runtime_settings(_base())


def test_production_rejects_memory_db():
    with pytest.raises(RuntimeError, match="DB_PROVIDER=mongodb"):
        validate_runtime_settings(_base(APP_ENV="production", DB_PROVIDER="memory"))


def test_production_rejects_docs_enabled():
    with pytest.raises(RuntimeError, match="ENABLE_DOCS"):
        validate_runtime_settings(
            _base(
                APP_ENV="production",
                DB_PROVIDER="mongodb",
                MONGODB_URL="mongodb://localhost:27017",
                ENABLE_DOCS=True,
                EVENT_BUS_BACKEND="outbox",
            )
        )


def test_production_requires_outbox():
    with pytest.raises(RuntimeError, match="EVENT_BUS_BACKEND=outbox"):
        validate_runtime_settings(
            _base(
                APP_ENV="production",
                DB_PROVIDER="mongodb",
                MONGODB_URL="mongodb://localhost:27017",
                ENABLE_DOCS=False,
                EVENT_BUS_BACKEND="memory",
            )
        )


def test_production_ok_with_outbox():
    validate_runtime_settings(
        _base(
            APP_ENV="production",
            DB_PROVIDER="mongodb",
            MONGODB_URL="mongodb://mongo:27017",
            ENABLE_DOCS=False,
            EVENT_BUS_BACKEND="outbox",
        )
    )
