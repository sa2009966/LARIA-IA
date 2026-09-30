"""Voz del tutor: convierte un trozo de su respuesta en audio (ADR-026)."""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from src.domain.ports.embodiment import AffectState, TextToSpeechPort
from src.domain.services.speakable import speakable_text
from src.infrastructure.config import settings
from src.interfaces.api.dependencies import get_current_user_id, get_text_to_speech
from src.interfaces.api.openapi_responses import RESP_401_UNAUTHORIZED, RESP_429_RATE_LIMIT

router = APIRouter(prefix="/speech", tags=["Voz"])


class SpeechRequest(BaseModel):
    #: Un trozo de la respuesta del tutor, tal como se escribió (con markdown):
    #: el servidor lo convierte en texto hablable.
    text: Annotated[str, Field(min_length=1, max_length=4000)]
    #: `payload.emotion` del envelope; decide el tono.
    emotion: Literal["calm", "encouraging", "patient", "celebratory"] = "encouraging"


class SpeechConfig(BaseModel):
    enabled: bool
    max_chars: int


@router.get("/config", response_model=SpeechConfig, summary="¿Está disponible la voz?")
async def speech_config():
    return SpeechConfig(enabled=bool(settings.TTS_ENABLED), max_chars=settings.TTS_MAX_CHARS)


@router.post(
    "",
    summary="Leer en voz alta un trozo de la respuesta del tutor",
    description=(
        "Devuelve `audio/mpeg` en streaming. El texto se limpia antes (sin markdown, "
        "fórmulas complejas, código ni esquemas: se avisa de que están en pantalla). "
        "**204** si no queda nada que decir. **503** si la voz está apagada o el proveedor "
        f"falla. Máximo {settings.TTS_MAX_CHARS} caracteres hablables por petición: el "
        "cliente trocea la respuesta por frases."
    ),
    responses={
        200: {"content": {"audio/mpeg": {}}, "description": "Audio MP3 en streaming."},
        204: {"description": "No hay nada que leer (solo código o esquemas)."},
        **RESP_401_UNAUTHORIZED,
        **RESP_429_RATE_LIMIT,
        503: {"description": "Voz no disponible."},
    },
)
async def speak(
    body: SpeechRequest,
    _: Annotated[str, Depends(get_current_user_id)],
    tts: Annotated[TextToSpeechPort, Depends(get_text_to_speech)],
):
    if not settings.TTS_ENABLED:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="La voz no está activada.")
    texto = speakable_text(body.text)
    if not texto:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    if len(texto) > settings.TTS_MAX_CHARS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Manda la respuesta por partes: máximo {settings.TTS_MAX_CHARS} caracteres por petición.",
        )
    afecto = AffectState(body.emotion)
    stream = getattr(tts, "stream", None)
    if stream is None:  # adaptador sin streaming (el nulo, en pruebas)
        audio = await tts.synthesize(texto, afecto)
        if not audio:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="La voz no está disponible.")
        return Response(content=audio, media_type="audio/mpeg")

    from src.infrastructure.embodiment.openai_tts import VoiceUnavailable

    trozos = stream(texto, afecto)
    # Se pide el primer trozo ANTES de responder: si el proveedor falla, el
    # cliente recibe un 503 con JSON en vez de un 200 con un audio cortado.
    try:
        primero = await trozos.__anext__()
    except (VoiceUnavailable, StopAsyncIteration):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="La voz no está disponible ahora mismo.")

    async def audio():
        yield primero
        try:
            async for trozo in trozos:
                yield trozo
        except VoiceUnavailable:
            return  # el audio queda corto; el texto sigue en pantalla

    return StreamingResponse(audio(), media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=86400"})
