"""Compresión gzip de las respuestas de la API (texto/JSON).

En datos móviles, un chat largo con todo su historial viajaba sin comprimir.
Quedan fuera, por ruta, lo que ya viene comprimido o es binario:
- la voz (`/speech`, MP3 en streaming): recomprimirla gasta CPU y retrasa el audio;
- el original de un documento (`/documents/{id}/content`: PDF, DOCX…).
El streaming del tutor (SSE) lo excluye Starlette por tipo de contenido.
"""
from __future__ import annotations

from starlette.middleware.gzip import GZipMiddleware

_SIN_COMPRIMIR = ("/api/v1/speech",)


class SelectiveGZipMiddleware:
    def __init__(self, app, minimum_size: int = 1000, compresslevel: int = 6) -> None:
        self.app = app
        # Nivel 6: casi la misma reducción que 9 con bastante menos CPU, que en
        # el plan gratuito de Render es escasa.
        self.gzip = GZipMiddleware(app, minimum_size=minimum_size, compresslevel=compresslevel)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path.startswith(_SIN_COMPRIMIR) or (path.startswith("/api/v1/documents/") and path.endswith("/content")):
                return await self.app(scope, receive, send)
            return await self.gzip(scope, receive, send)
        return await self.app(scope, receive, send)
