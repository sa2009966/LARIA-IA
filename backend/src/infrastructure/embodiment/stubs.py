"""Adaptadores nulos de embodiment: sin micrófono, altavoz ni hardware.

Timeouts y métricas aíslan fallos del dispositivo del núcleo pedagógico.
"""
from __future__ import annotations

import asyncio
import logging
import time

from src.domain.ports.embodiment import (
    AffectState,
    PresencePort,
    SpeechToTextPort,
    TextToSpeechPort,
)
from src.domain.ports.metrics_port import MetricsPort

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S = 2.0


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
