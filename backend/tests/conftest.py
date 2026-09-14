"""Configuración raíz de pytest: entorno aislado antes de importar la app.

Fuerza backends in-memory para que un `.env` local con Mongo no cuelgue TestClient
(lifespan → ensure_mongo_indexes). No importar `src.*` a nivel de módulo aquí.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Forzar (no setdefault): el .env del desarrollador no debe contaminar la suite.
os.environ["SECRET_KEY"] = "a" * 64
os.environ["OPENAI_API_KEY"] = "sk-test-not-a-real-key"
os.environ["IA_PROVIDER"] = "openai"
os.environ["DB_PROVIDER"] = "memory"
os.environ["EVENT_BUS_BACKEND"] = "memory"
os.environ["RATE_LIMIT_BACKEND"] = "memory"
os.environ["CACHE_BACKEND"] = "memory"
os.environ["ENABLE_DOCS"] = "true"
os.environ["DEBUG"] = "false"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["APP_ENV"] = "development"
os.environ["METRICS_ENABLED"] = "true"
os.environ["EMBODIMENT_ENABLED"] = "false"

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_MEMORY_BACKENDS = (
    ("DB_PROVIDER", "memory"),
    ("EVENT_BUS_BACKEND", "memory"),
    ("RATE_LIMIT_BACKEND", "memory"),
    ("CACHE_BACKEND", "memory"),
)

_CACHE_NAMES = (
    "get_user_repo",
    "get_document_repo",
    "get_document_blob_store",
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
    "get_text_to_speech",
    "get_presence",
    "get_device_command",
    "get_sensor_input",
    "get_affect_policy",
)


def clear_dependency_caches() -> None:
    from src.interfaces.api import dependencies as deps

    for name in _CACHE_NAMES:
        fn = getattr(deps, name, None)
        if fn is not None and hasattr(fn, "cache_clear"):
            fn.cache_clear()


def _force_memory_backends() -> None:
    for key, value in _MEMORY_BACKENDS:
        os.environ[key] = value


def _assert_settings_use_memory() -> None:
    from src.infrastructure.config import settings

    assert settings.DB_PROVIDER == "memory", (
        "Tests deben forzar DB_PROVIDER=memory (evita hang TestClient→Mongo). "
        f"Actual={settings.DB_PROVIDER!r}. Revisa orden de imports / conftest."
    )
    assert (settings.EVENT_BUS_BACKEND or "memory").lower() == "memory"
    assert (settings.RATE_LIMIT_BACKEND or "memory").lower() == "memory"
    assert (settings.CACHE_BACKEND or "memory").lower() == "memory"


def _patch_bcrypt_for_tests() -> None:
    """Baja el coste de bcrypt solo en el proceso de pytest; producción no cambia."""
    import bcrypt

    original = bcrypt.gensalt

    def _fast_gensalt(rounds: int = 12, prefix: bytes = b"2b"):  # noqa: ARG001
        return original(4, prefix)

    bcrypt.gensalt = _fast_gensalt  # type: ignore[method-assign]


def pytest_configure(config) -> None:  # noqa: ARG001
    """Garantiza backends memory y bcrypt barato antes de colectar tests."""
    _force_memory_backends()
    _patch_bcrypt_for_tests()


def pytest_sessionstart(session) -> None:  # noqa: ARG001
    """Falla al arrancar la sesión si el singleton Settings ya nació contaminado."""
    _force_memory_backends()
    _assert_settings_use_memory()


import pytest


@pytest.fixture(autouse=True)
def _assert_test_backends_isolated():
    """Falla temprano si el .env o un import prematuro contaminó Settings."""
    _assert_settings_use_memory()
    yield
