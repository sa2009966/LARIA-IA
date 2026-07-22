import pytest

from src.domain.ports.embodiment import AffectState
from src.domain.services.affect_policy import AffectPolicy
from src.infrastructure.config import settings
from src.infrastructure.embodiment.stubs import (
    LogOnlyPresence,
    NullSpeechToText,
    NullTextToSpeech,
)


@pytest.mark.asyncio
async def test_null_stt_tts_presence_no_crash():
    assert await NullSpeechToText().transcribe(b"x") == ""
    assert await NullTextToSpeech().synthesize("hola", AffectState.CALM) == b""
    await LogOnlyPresence().express(AffectState.ENCOURAGING, "ok")


def test_embodiment_flag_default_off():
    assert settings.EMBODIMENT_ENABLED is False


def test_affect_policy_celebratory_on_high_score():
    assert AffectPolicy().select(None, None, last_score_ratio=0.9) == AffectState.CELEBRATORY
