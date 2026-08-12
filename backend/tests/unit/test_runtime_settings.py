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
    return Settings(_env_file=None, **data)


def _prod_ok(**kwargs) -> Settings:
    defaults = {
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
    defaults.update(kwargs)
    return _base(**defaults)


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


def test_production_requires_redis_rate_limit():
    with pytest.raises(RuntimeError, match="RATE_LIMIT_BACKEND=redis"):
        validate_runtime_settings(
            _prod_ok(RATE_LIMIT_BACKEND="memory")
        )


def test_production_requires_redis_cache():
    with pytest.raises(RuntimeError, match="CACHE_BACKEND=redis"):
        validate_runtime_settings(_prod_ok(CACHE_BACKEND="memory"))


def test_production_requires_redis_url():
    with pytest.raises(RuntimeError, match="REDIS_URL"):
        validate_runtime_settings(_prod_ok(REDIS_URL="   "))


def test_production_requires_rate_limit_enabled():
    with pytest.raises(RuntimeError, match="RATE_LIMIT_ENABLED"):
        validate_runtime_settings(_prod_ok(RATE_LIMIT_ENABLED=False))


def test_production_rejects_empty_cors():
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        validate_runtime_settings(_prod_ok(CORS_ORIGINS=[]))


def test_production_rejects_wildcard_cors():
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        validate_runtime_settings(_prod_ok(CORS_ORIGINS=["*"]))


def test_production_ok_with_outbox_and_redis():
    validate_runtime_settings(_prod_ok())


def test_production_ok_with_local_front_cors():
    """Compose local + front en :4321 sigue siendo forma de producción temprana."""
    validate_runtime_settings(
        _prod_ok(CORS_ORIGINS=["http://localhost:4321", "http://localhost:3000"])
    )
