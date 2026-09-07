"""Puertos de embodiment (voz/presencia/dispositivo). Pedagogía no depende de hardware."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class AffectState(str, Enum):
    CALM = "calm"
    ENCOURAGING = "encouraging"
    PATIENT = "patient"
    CELEBRATORY = "celebratory"


class SafetyClass(str, Enum):
    INFO = "info"
    MOTION = "motion"
    ESTOP = "estop"


class DeviceCommandKind(str, Enum):
    LED = "led"
    GESTURE = "gesture"
    SPEAK = "speak"
    STOP = "stop"


@dataclass(frozen=True)
class DeviceCommand:
    kind: DeviceCommandKind
    payload: dict[str, Any] = field(default_factory=dict)
    timeout_ms: int = 500
    safety_class: SafetyClass = SafetyClass.INFO
    command_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class CommandAck:
    command_id: UUID
    ok: bool
    detail: str = ""
    degraded: bool = False


@dataclass(frozen=True)
class SensorReading:
    kind: str  # mic|imu|proximity|button|...
    payload: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


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


class DeviceCommandPort(ABC):
    """Actuadores físicos. Nunca decide pedagogía."""

    @abstractmethod
    async def send(self, command: DeviceCommand) -> CommandAck:
        ...


class SensorInputPort(ABC):
    """Sensores. Lecturas sanitizadas; sin audio raw en el bus pedagógico."""

    @abstractmethod
    async def poll(self) -> SensorReading | None:
        ...
