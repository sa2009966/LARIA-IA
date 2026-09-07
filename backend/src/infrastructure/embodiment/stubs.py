"""Adaptadores nulos de embodiment: sin micrófono, altavoz ni hardware.

Timeouts y métricas aíslan fallos del dispositivo del núcleo pedagógico.
"""
from __future__ import annotations

import asyncio
import logging
import time

from src.domain.ports.embodiment import (
    AffectState,
    CommandAck,
    DeviceCommand,
    DeviceCommandPort,
    PresencePort,
    SafetyClass,
    SensorInputPort,
    SensorReading,
    SpeechToTextPort,
    TextToSpeechPort,
)
from src.domain.ports.metrics_port import MetricsPort

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S = 2.0
_DEVICE_TIMEOUT_S = 0.5


class NullSpeechToText(SpeechToTextPort):
    def __init__(
        self,
        *,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        metrics: MetricsPort | None = None,
    ) -> None:
        self._timeout_s = timeout_s
        self._metrics = metrics

    async def _do_transcribe(self, audio_bytes: bytes) -> str:
        _ = audio_bytes
        return ""

    async def transcribe(self, audio_bytes: bytes) -> str:
        started = time.perf_counter()
        try:
            text = await asyncio.wait_for(
                self._do_transcribe(audio_bytes),
                timeout=self._timeout_s,
            )
            if self._metrics:
                self._metrics.observe(
                    "speech_latency",
                    (time.perf_counter() - started) * 1000.0,
                    component="stt",
                )
            return text
        except Exception:
            logger.exception("embodiment_stt_failed")
            if self._metrics:
                self._metrics.incr("command_failed", component="stt")
                self._metrics.incr("device_errors", component="stt")
            return ""


class NullTextToSpeech(TextToSpeechPort):
    def __init__(
        self,
        *,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        metrics: MetricsPort | None = None,
    ) -> None:
        self._timeout_s = timeout_s
        self._metrics = metrics

    async def _do_synthesize(self, text: str, affect: AffectState) -> bytes:
        _ = text, affect
        return b""

    async def synthesize(self, text: str, affect: AffectState) -> bytes:
        started = time.perf_counter()
        try:
            audio = await asyncio.wait_for(
                self._do_synthesize(text, affect),
                timeout=self._timeout_s,
            )
            if self._metrics:
                self._metrics.observe(
                    "speech_latency",
                    (time.perf_counter() - started) * 1000.0,
                    component="tts",
                )
            return audio
        except Exception:
            logger.exception("embodiment_tts_failed")
            if self._metrics:
                self._metrics.incr("command_failed", component="tts")
                self._metrics.incr("device_errors", component="tts")
            return b""


class LogOnlyPresence(PresencePort):
    def __init__(
        self,
        *,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        metrics: MetricsPort | None = None,
    ) -> None:
        self._timeout_s = timeout_s
        self._metrics = metrics

    async def _do_express(self, affect: AffectState, message: str | None) -> None:
        logger.debug("presence.express affect=%s message=%s", affect.value, message)

    async def express(self, affect: AffectState, message: str | None = None) -> None:
        try:
            await asyncio.wait_for(
                self._do_express(affect, message),
                timeout=self._timeout_s,
            )
            if self._metrics:
                self._metrics.incr("device_presence", affect=affect.value)
        except Exception:
            logger.exception("embodiment_presence_failed")
            if self._metrics:
                self._metrics.incr("command_failed", component="presence")
                self._metrics.incr("device_errors", component="presence")


class NullDeviceCommand(DeviceCommandPort):
    """No-op con allowlist de safety: MOTION/ESTOP se registran pero no ejecutan hardware."""

    def __init__(
        self,
        *,
        timeout_s: float = _DEVICE_TIMEOUT_S,
        metrics: MetricsPort | None = None,
        degraded: bool = False,
    ) -> None:
        self._timeout_s = timeout_s
        self._metrics = metrics
        self._degraded = degraded
        if metrics:
            metrics.gauge("embodiment_degraded", 1.0 if degraded else 0.0)

    async def send(self, command: DeviceCommand) -> CommandAck:
        started = time.perf_counter()
        if command.safety_class == SafetyClass.ESTOP:
            if self._metrics:
                self._metrics.incr("safety_interlock", kind="estop")
            return CommandAck(command_id=command.command_id, ok=True, detail="estop_ack")
        if self._degraded:
            if self._metrics:
                self._metrics.incr("affect_render_skipped", reason="degraded")
            return CommandAck(
                command_id=command.command_id,
                ok=False,
                detail="degraded",
                degraded=True,
            )
        if command.safety_class == SafetyClass.MOTION:
            if self._metrics:
                self._metrics.incr("forbidden_command_blocked", kind=command.kind.value)
            # Stub: no ejecuta motion real; acusa bloqueo seguro.
            return CommandAck(
                command_id=command.command_id,
                ok=False,
                detail="motion_blocked_in_stub",
            )
        try:
            await asyncio.wait_for(asyncio.sleep(0), timeout=self._timeout_s)
            if self._metrics:
                self._metrics.observe(
                    "device_command_latency",
                    (time.perf_counter() - started) * 1000.0,
                    kind=command.kind.value,
                )
            return CommandAck(command_id=command.command_id, ok=True, detail="noop")
        except asyncio.TimeoutError:
            if self._metrics:
                self._metrics.incr("device_command_timeout", kind=command.kind.value)
            return CommandAck(command_id=command.command_id, ok=False, detail="timeout")


class NullSensorInput(SensorInputPort):
    def __init__(self, *, metrics: MetricsPort | None = None) -> None:
        self._metrics = metrics

    async def poll(self) -> SensorReading | None:
        _ = self._metrics
        return None
