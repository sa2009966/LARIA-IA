from src.infrastructure.config import settings
from src.infrastructure.ia.base_chat_analyst import BaseChatAnalyst
from src.domain.ports.metrics_port import MetricsPort

_OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIAnalyst(BaseChatAnalyst):

    def __init__(self, metrics: MetricsPort | None = None) -> None:
        super().__init__(
            api_url=_OPENAI_API_URL,
            model=settings.OPENAI_MODEL_DEFAULT or settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            metrics=metrics,
        )
