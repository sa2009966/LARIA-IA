"""Modelos de dominio (entidades).

Las definiciones concretas viven en `entities/`; este módulo ofrece un punto
de importación único (`User`, `Document`, `Analysis`).
"""

from src.domain.entities.analysis import Analysis
from src.domain.entities.document import Document
from src.domain.entities.user import User

__all__ = ["Analysis", "Document", "User"]
