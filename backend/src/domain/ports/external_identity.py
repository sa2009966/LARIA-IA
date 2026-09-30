"""Identidad verificada por un proveedor externo (Google)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ExternalIdentity:
    subject: str
    email: str
    name: str = ""


class InvalidExternalToken(ValueError):
    """El token no es válido, no es para esta app o el correo no está verificado."""


class ExternalIdentityVerifier(ABC):
    @abstractmethod
    async def verify(self, token: str) -> ExternalIdentity:
        """Devuelve la identidad o lanza `InvalidExternalToken`."""
