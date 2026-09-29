"""Lo que el tutor recuerda de un chat: resumen de lo antiguo y lo reciente (ADR-021)."""
from __future__ import annotations

import logging

from src.domain.aggregates.chat import ChatAggregate
from src.domain.ports.chat_title_generator import ConversationSummarizer

logger = logging.getLogger("laria.chat")


class ConversationMemory:
    def __init__(self, summarizer: ConversationSummarizer | None = None) -> None:
        self._summarizer = summarizer

    async def recall(self, chat: ChatAggregate) -> tuple[tuple[str, str], ...]:
        """La memoria del chat para este turno. Si toca, antes actualiza el resumen.

        Muta `chat` (resumen y hasta dónde cubre); quien llama lo guarda con el
        resto del turno. Si el modelo falla, el turno sigue: lo pendiente espera
        en la conversación reciente y se reintenta en el siguiente mensaje.
        """
        pendientes = chat.messages_to_summarize()
        if pendientes and self._summarizer is not None:
            try:
                nuevo = await self._summarizer.summarize_conversation(chat.summary, pendientes)
                chat.absorb_summary(nuevo, len(pendientes))
            except Exception:  # noqa: BLE001 — sin resumen nuevo el turno sigue
                logger.warning("chat_summary_failed chat=%s pendientes=%d", chat.id, len(pendientes))
        return chat.memory()
