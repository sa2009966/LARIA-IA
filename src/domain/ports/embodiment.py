"""Puertos de embodiment (voz/presencia). Pedagogía no depende de hardware."""
from abc import ABC, abstractmethod
from enum import Enum


class AffectState(str, Enum):
    CALM = "calm"
    ENCOURAGING = "encouraging"
    PATIENT = "patient"
    CELEBRATORY = "celebratory"


class SpeechToTextPort(ABC):
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes) -> str:
        ...


class TextToSpeechPort(ABC):
    @abstractmethod
    async def synthesize(self, text: str, affect: AffectState) -> bytes:
        ...


class PresencePort(ABC):
    @abstractmethod
    async def express(self, affect: AffectState, message: str | None = None) -> None:
        ...
