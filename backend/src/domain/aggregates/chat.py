from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ChatMessage:
    id: UUID = field(default_factory=uuid4)
    role: Literal["user", "assistant", "system"] = "user"
    content: str = ""
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)


@dataclass
class ChatAggregate:
    """Conversación del estudiante con el tutor. Wrapper de persistencia para el frontend."""

    id: UUID = field(default_factory=uuid4)
    owner_id: UUID = field(default_factory=uuid4)
    title: str = "Nuevo chat"
    document_id: UUID | None = None
    messages: list[ChatMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    @staticmethod
    def create(
        owner_id: UUID,
        title: str | None = None,
        document_id: UUID | None = None,
    ) -> "ChatAggregate":
        t = (title or "Nuevo chat").strip()
        if not t:
            t = "Nuevo chat"
        if len(t) > 200:
            t = t[:200]
        return ChatAggregate(
            owner_id=owner_id,
            title=t,
            document_id=document_id,
        )

    def add_message(
        self,
        role: Literal["user", "assistant", "system"],
        content: str,
        metadata: dict | None = None,
    ) -> ChatMessage:
        if not content or not content.strip():
            raise ValueError("El contenido del mensaje no puede estar vacío")
        msg = ChatMessage(
            role=role,
            content=content.strip(),
            metadata=metadata or {},
        )
        self.messages.append(msg)
        self.updated_at = _utc_now()
        return msg

    def set_title(self, title: str) -> None:
        t = title.strip()
        if not t:
            raise ValueError("El título no puede estar vacío")
        self.title = t[:200]
        self.updated_at = _utc_now()

    def link_document(self, document_id: UUID) -> None:
        self.document_id = document_id
        self.updated_at = _utc_now()
