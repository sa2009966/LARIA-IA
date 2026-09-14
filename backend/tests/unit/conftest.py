"""Configuración compartida para pruebas unitarias del backend."""

# La raíz tests/conftest.py ya fuerza el entorno; aquí solo path.
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
