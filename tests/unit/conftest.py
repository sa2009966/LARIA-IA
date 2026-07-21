"""Configuración compartida para pruebas unitarias del backend."""

import os
import sys
from pathlib import Path

# Entorno mínimo antes de importar src (settings se carga al importar).
os.environ.setdefault("SECRET_KEY", "a" * 64)
os.environ.setdefault("OPENAI_API_KEY", "sk-test-not-a-real-key")
os.environ.setdefault("IA_PROVIDER", "openai")
os.environ.setdefault("DB_PROVIDER", "memory")
os.environ.setdefault("ENABLE_DOCS", "true")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
