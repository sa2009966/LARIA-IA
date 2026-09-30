"""Cabeceras de seguridad en todas las respuestas de la API.

ASGI puro y no BaseHTTPMiddleware: solo toca las cabeceras al empezar la
respuesta, así que no bufferiza el streaming SSE del tutor.
"""
from __future__ import annotations

_CABECERAS: tuple[tuple[bytes, bytes], ...] = (
    # El navegador no adivina tipos: un .txt subido no se ejecuta como HTML.
    (b"x-content-type-options", b"nosniff"),
    # La API no se enmarca. El visor del frontend descarga el archivo y lo muestra
    # desde su propio origen, así que no la necesita en un iframe.
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    # Solo HTTPS durante un año (Render siempre sirve HTTPS).
    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
    (b"cross-origin-opener-policy", b"same-origin"),
)


class SecurityHeadersMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def enviar(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                presentes = {k.lower() for k, _ in headers}
                headers.extend((k, v) for k, v in _CABECERAS if k not in presentes)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, enviar)
