from src.infrastructure.kimi.kimi_ia_analyst import KimiIAAnalyst
from src.infrastructure.openai.openai_ia_analyst import OpenAIAnalyst


def test_provider_defaults_to_kimi():
    from src.infrastructure.config import settings
    assert settings.IA_PROVIDER == "kimi"


def test_kimi_implements_ia_analyst():
    from src.domain.ports.ia_analyst import IAAnalyst
    assert isinstance(KimiIAAnalyst(), IAAnalyst)


def test_openai_implements_ia_analyst():
    from src.domain.ports.ia_analyst import IAAnalyst
    assert isinstance(OpenAIAnalyst(), IAAnalyst)