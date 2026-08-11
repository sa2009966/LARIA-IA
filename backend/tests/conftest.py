"""Configuración raíz de pytest: entorno aislado antes de importar la app.

Fuerza backends in-memory para que un `.env` local con Mongo no cuelgue TestClient
(lifespan → ensure_mongo_indexes).
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
    "get_speech_to_text",
    "get_text_to_speech",
    "get_presence",
    "get_affect_policy",
)


def clear_dependency_caches() -> None:
    from src.interfaces.api import dependencies as deps

    for name in _CACHE_NAMES:
        fn = getattr(deps, name, None)
        if fn is not None and hasattr(fn, "cache_clear"):
            fn.cache_clear()
