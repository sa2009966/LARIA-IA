from typing import Optional
from uuid import UUID

from src.domain.aggregates.chat import ChatAggregate
from src.domain.ports.repositories import ChatRepository


class InMemoryChatRepository(ChatRepository):

    def __init__(self) -> None:
        self._chats: dict[UUID, ChatAggregate] = {}

    async def find_by_id(self, chat_id: UUID) -> Optional[ChatAggregate]:
        return self._chats.get(chat_id)

    async def find_by_owner(self, owner_id: UUID) -> list[ChatAggregate]:
        chats = [c for c in self._chats.values() if c.owner_id == owner_id]
        chats.sort(key=lambda c: c.updated_at, reverse=True)
        for c in chats:
            c.messages = []
        return chats

    async def save(self, chat: ChatAggregate) -> None:
        self._chats[chat.id] = chat

    async def delete(self, chat_id: UUID) -> None:
        self._chats.pop(chat_id, None)
