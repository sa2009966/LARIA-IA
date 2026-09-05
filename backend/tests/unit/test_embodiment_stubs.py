import pytest

from src.domain.ports.embodiment import (
    AffectState,
    DeviceCommand,
    DeviceCommandKind,
    SafetyClass,
)
from src.domain.services.affect_policy import AffectPolicy
from src.infrastructure.config import settings
from src.infrastructure.embodiment.stubs import (
    LogOnlyPresence,
    NullDeviceCommand,
    NullSensorInput,
    NullSpeechToText,
    NullTextToSpeech,
)
from src.infrastructure.metrics.in_memory_metrics import InMemoryMetrics


class _FailingTTS(NullTextToSpeech):
    async def _do_synthesize(self, text: str, affect: AffectState) -> bytes:
        raise RuntimeError("tts hardware offline")


class _FailingSTT(NullSpeechToText):
    async def _do_transcribe(self, audio_bytes: bytes) -> str:
        raise RuntimeError("mic offline")


@pytest.mark.asyncio
async def test_null_stt_tts_presence_no_crash():
    assert await NullSpeechToText().transcribe(b"x") == ""
    assert await NullTextToSpeech().synthesize("hola", AffectState.CALM) == b""
    await LogOnlyPresence().express(AffectState.ENCOURAGING, "ok")


def test_embodiment_flag_default_off():
    assert settings.EMBODIMENT_ENABLED is False


def test_affect_policy_celebratory_on_high_score():
    assert AffectPolicy().select(None, None, last_score_ratio=0.9) == AffectState.CELEBRATORY


@pytest.mark.asyncio
async def test_tts_failure_swallowed_with_metrics():
    metrics = InMemoryMetrics()
    audio = await _FailingTTS(metrics=metrics).synthesize("hola", AffectState.CALM)
    assert audio == b""
    snap = metrics.snapshot()
    assert any("command_failed" in k for k in snap["counters"])


@pytest.mark.asyncio
async def test_stt_failure_swallowed_with_metrics():
    metrics = InMemoryMetrics()
    text = await _FailingSTT(metrics=metrics).transcribe(b"wav")
    assert text == ""
    snap = metrics.snapshot()
    assert any("device_errors" in k for k in snap["counters"])


@pytest.mark.asyncio
async def test_device_command_stub_blocks_motion_and_acks_info():
    metrics = InMemoryMetrics()
    port = NullDeviceCommand(metrics=metrics)
    info = await port.send(DeviceCommand(kind=DeviceCommandKind.LED, safety_class=SafetyClass.INFO))
    assert info.ok is True
    motion = await port.send(
        DeviceCommand(kind=DeviceCommandKind.GESTURE, safety_class=SafetyClass.MOTION)
    )
    assert motion.ok is False
    assert "blocked" in motion.detail
    snap = metrics.snapshot()
    assert any("forbidden_command_blocked" in k for k in snap["counters"])


@pytest.mark.asyncio
async def test_stt_success_records_latency_metric():
    metrics = InMemoryMetrics()

    class _OkSTT(NullSpeechToText):
        async def _do_transcribe(self, audio_bytes: bytes) -> str:
            return "hola"

    text = await _OkSTT(metrics=metrics).transcribe(b"wav")
    assert text == "hola"
    snap = metrics.snapshot()
    assert any("speech_latency" in k for k in snap["histograms"])


@pytest.mark.asyncio
async def test_tts_success_records_latency_metric():
    metrics = InMemoryMetrics()

    class _OkTTS(NullTextToSpeech):
        async def _do_synthesize(self, text: str, affect: AffectState) -> bytes:
            return b"audio"

    audio = await _OkTTS(metrics=metrics).synthesize("hola", AffectState.CALM)
    assert audio == b"audio"
    snap = metrics.snapshot()
    assert any("speech_latency" in k for k in snap["histograms"])


@pytest.mark.asyncio
async def test_presence_express_with_metrics():
    metrics = InMemoryMetrics()
    await LogOnlyPresence(metrics=metrics).express(AffectState.CALM, "mensaje")
    snap = metrics.snapshot()
    assert snap["counters"] or snap["histograms"]


@pytest.mark.asyncio
async def test_degraded_skips_actuators():
    metrics = InMemoryMetrics()
    port = NullDeviceCommand(metrics=metrics, degraded=True)
    ack = await port.send(DeviceCommand(kind=DeviceCommandKind.SPEAK))
    assert ack.degraded is True
    assert await NullSensorInput().poll() is None
