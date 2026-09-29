from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, Sequence


@dataclass(frozen=True)
class TitleMessage:
    role: Literal["user", "assistant", "system"]
    content: str


class ChatTitleGenerator(ABC):
    """Puerto para generar el título inicial de una conversación."""

    @abstractmethod
    async def generate_chat_title(self, messages: Sequence[TitleMessage]) -> str:
        ...
