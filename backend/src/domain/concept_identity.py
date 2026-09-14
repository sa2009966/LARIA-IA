"""Identidad canónica de conceptos pedagógicos (una sola clave en todo el dominio)."""
from __future__ import annotations

import re
import unicodedata

_WS = re.compile(r"\s+")


def canonicalize_concept(label: str) -> str:
    """Fold NFKD, minúsculas, recorte y espacios colapsados.

    'Ecuación', 'ecuacion' y 'ecuación' producen la misma clave.
    """
    text = unicodedata.normalize("NFKD", label or "")
    folded = "".join(c for c in text if not unicodedata.combining(c))
    return _WS.sub(" ", folded.strip().lower())
