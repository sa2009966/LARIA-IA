from datetime import datetime
from typing import Annotated, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ChatCreateRequest(BaseModel):
    title: Annotated[Optional[str], Field(max_length=200)] = None
    document_id: Annotated[Optional[UUID], Field(description="Opcional: linkar a un documento existente")] = None


class ChatAddMessageRequest(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: Annotated[str, Field(min_length=1)]
    metadata: Optional[dict] = None


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    metadata: dict = {}
    created_at: datetime


class ChatResponse(BaseModel):
    id: str
    title: str
    document_id: Optional[str] = None
    messages: list[ChatMessageResponse] = []
    created_at: datetime
    updated_at: datetime


class ChatSummary(BaseModel):
    id: str
    title: str
    document_id: Optional[str] = None
    message_count: int
    last_message_preview: str = ""
    created_at: datetime
    updated_at: datetime


class ChatListResponse(BaseModel):
    chats: list[ChatSummary]
