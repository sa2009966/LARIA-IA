"""Voz del tutor con OpenAI (ADR-026).

El tono sale de `AffectState`, que decide el dominio (ADR-002): la voz no
inventa emociones, pone en sonido la que la política afectiva ya eligió.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import httpx

from src.domain.ports.embodiment import AffectState, TextToSpeechPort

logger = logging.getLogger("laria.voz")

API_URL = "https://api.openai.com/v1/audio/speech"

_BASE = (
    "Eres LARIA, la tutora de Plenum. Habla en español latino neutro, con dicción "
    "clara y un ritmo pausado de clase, sin sonar robótica ni teatral."
)
_TONO = {
    AffectState.CALM: "Tono sereno y cercano.",
    AffectState.ENCOURAGING: "Tono cálido y animado, como quien confía en el estudiante.",
    AffectState.PATIENT: "Tono paciente y tranquilizador, un poco más despacio: el estudiante está atascado.",
    AffectState.CELEBRATORY: "Tono alegre y orgulloso: el estudiante acaba de lograr algo.",
}


class VoiceUnavailable(RuntimeError):
    """El proveedor de voz falló; el texto sigue estando en pantalla."""


class OpenAITextToSpeech(TextToSpeechPort):
    def __init__(self, api_key: str, model: str, voice: str, client: httpx.AsyncClient | None = None) -> None:
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._model = model
        self._voice = voice
        self._client = client

    def _payload(self, text: str, affect: AffectState) -> dict:
        return {
            "model": self._model,
            "voice": self._voice,
            "input": text,
            "instructions": f"{_BASE} {_TONO.get(affect, '')}",
            "response_format": "mp3",
        }

    async def stream(self, text: str, affect: AffectState) -> AsyncIterator[bytes]:
        """MP3 en trozos, según llegan: el primer audio suena a los ~2 s y no al final."""
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))
        try:
            async with client.stream("POST", API_URL, headers=self._headers, json=self._payload(text, affect)) as r:
                if r.status_code != 200:
                    cuerpo = (await r.aread())[:200]
                    logger.error("tts_fallo http=%s cuerpo=%s", r.status_code, cuerpo)
                    raise VoiceUnavailable("La voz no está disponible ahora mismo.")
                async for chunk in r.aiter_bytes():
                    yield chunk
        except httpx.HTTPError as exc:
            logger.error("tts_fallo %s", type(exc).__name__)
            raise VoiceUnavailable("La voz no está disponible ahora mismo.") from exc
        finally:
            if self._client is None:
                await client.aclose()

    async def synthesize(self, text: str, affect: AffectState) -> bytes:
        return b"".join([c async for c in self.stream(text, affect)])
