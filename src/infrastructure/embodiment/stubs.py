"""Adaptadores nulos de embodiment: sin micrófono, altavoz ni hardware."""
import logging

from src.domain.ports.embodiment import (
    AffectState,
    PresencePort,
    SpeechToTextPort,
    TextToSpeechPort,
)

logger = logging.getLogger(__name__)


class NullSpeechToText(SpeechToTextPort):
    async def transcribe(self, audio_bytes: bytes) -> str:
        return ""


class NullTextToSpeech(TextToSpeechPort):
    async def synthesize(self, text: str, affect: AffectState) -> bytes:
        return b""


class LogOnlyPresence(PresencePort):
    async def express(self, affect: AffectState, message: str | None = None) -> None:
        logger.debug("presence.express affect=%s message=%s", affect.value, message)
