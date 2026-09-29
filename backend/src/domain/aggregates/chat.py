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


#: Mensajes recientes que ve el tutor, y cuánto texto como máximo. Tres o cuatro
#: intercambios bastan para la continuidad —a qué se refiere "las guerras", cómo
#: se llama el estudiante— sin que un chat largo se coma el presupuesto de tokens
#: de cada turno.
HISTORY_MAX_MESSAGES = 8
HISTORY_MAX_CHARS = 4000
_HISTORY_MAX_PER_MESSAGE = 700


def recent_history(
    messages: list[ChatMessage],
    max_messages: int = HISTORY_MAX_MESSAGES,
    max_chars: int = HISTORY_MAX_CHARS,
) -> tuple[tuple[str, str], ...]:
    """La conversación reciente, de más antigua a más reciente: `(rol, texto)`.

    Solo cuenta lo que dijeron el estudiante y el tutor. Los mensajes `system`
    —notas como "📎 Subí el archivo" o avisos de error— no son diálogo, y un
    "no pude generar una respuesta" en la memoria solo confundiría al modelo.

    Si no cabe todo, se sacrifica lo más antiguo: para dar continuidad importa lo
    último que se dijo.
    """
    dialogo = [m for m in messages if m.role in ("user", "assistant") and m.content.strip()]
    elegidos: list[tuple[str, str]] = []
    total = 0
    for m in reversed(dialogo[-max_messages:]):
        texto = " ".join(m.content.split())
        if len(texto) > _HISTORY_MAX_PER_MESSAGE:
            texto = texto[:_HISTORY_MAX_PER_MESSAGE].rsplit(" ", 1)[0] + " […]"
        if total + len(texto) > max_chars:
            break
        elegidos.append((m.role, texto))
        total += len(texto)
    return tuple(reversed(elegidos))
