"""Verificación del ID token de "Continuar con Google" (ADR-025).

Se verifica con las claves públicas de Google (JWKS), sin la librería oficial:
PyJWT + cryptography ya están. Lo que se comprueba es lo que Google exige:
firma RS256, emisor, audiencia (NUESTRO client id: un token emitido para otra app
no sirve aquí), caducidad y correo verificado.
"""
from __future__ import annotations

import asyncio

import jwt
from jwt import PyJWKClient

from src.domain.ports.external_identity import (
    ExternalIdentity,
    ExternalIdentityVerifier,
    InvalidExternalToken,
)

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")


class GoogleIdentityVerifier(ExternalIdentityVerifier):
    def __init__(self, client_id: str, jwks_client: PyJWKClient | None = None) -> None:
        self._client_id = (client_id or "").strip()
        # Las claves se cachean: Google las rota cada pocos días, no en cada login.
        self._jwks = jwks_client or PyJWKClient(GOOGLE_JWKS_URL, cache_keys=True, lifespan=3600)

    async def verify(self, token: str) -> ExternalIdentity:
        if not self._client_id:
            raise InvalidExternalToken("El acceso con Google no está configurado.")
        # PyJWKClient descarga con urllib (bloqueante): fuera del event loop.
        return await asyncio.to_thread(self._verify_sync, token)

    def _verify_sync(self, token: str) -> ExternalIdentity:
        try:
            clave = self._jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                clave,
                algorithms=["RS256"],
                audience=self._client_id,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
                leeway=30,
            )
        except (jwt.PyJWTError, ValueError) as exc:
            raise InvalidExternalToken("El inicio de sesión con Google no es válido.") from exc
        if claims.get("iss") not in GOOGLE_ISSUERS:
            raise InvalidExternalToken("El inicio de sesión con Google no es válido.")
        email = (claims.get("email") or "").strip().lower()
        if not email or claims.get("email_verified") not in (True, "true"):
            raise InvalidExternalToken("Tu cuenta de Google no tiene un correo verificado.")
        return ExternalIdentity(subject=str(claims["sub"]), email=email, name=claims.get("name") or "")
