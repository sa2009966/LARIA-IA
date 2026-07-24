from src.domain.ports.ia_analyst import IAAnalyst
from src.infrastructure.config import Settings, validate_ia_settings
from src.infrastructure.openai.openai_ia_analyst import OpenAIAnalyst


def test_provider_defaults_to_openai():
    s = Settings(
        SECRET_KEY="a" * 64,
        OPENAI_API_KEY="sk-test",
        IA_PROVIDER="openai",
        _env_file=None,
    )
    assert s.IA_PROVIDER == "openai"


def test_openai_implements_ia_analyst():
    assert isinstance(OpenAIAnalyst(), IAAnalyst)


def test_validate_ia_rejects_kimi():
    s = Settings(
        SECRET_KEY="a" * 64,
        OPENAI_API_KEY="sk-test",
        IA_PROVIDER="kimi",
        _env_file=None,
    )
    try:
        validate_ia_settings(s)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "openai" in str(exc).lower()


def test_validate_ia_requires_api_key():
    s = Settings(
        SECRET_KEY="a" * 64,
        OPENAI_API_KEY="",
        IA_PROVIDER="openai",
        _env_file=None,
    )
    try:
        validate_ia_settings(s)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "OPENAI_API_KEY" in str(exc)
