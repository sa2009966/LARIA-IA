from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.services.chat_tutor_service import ChatTutorService
from src.domain.aggregates.chat import ChatAggregate
from src.domain.ports.repositories import ChatRepository
from src.interfaces.api.dependencies import (
    get_chat_repo,
    get_chat_tutor_service,
    get_current_user_id,
)
from src.interfaces.schemas.chat_schemas import (
    ChatAddMessageRequest,
    ChatCreateRequest,
    ChatListResponse,
    ChatMessageResponse,
    ChatResponse,
    ChatSummary,
)

router = APIRouter(prefix="/chats", tags=["Chats"])

_MSG_NO_ENCONTRADO = "Recurso no encontrado"


def _map_chat(chat: ChatAggregate) -> ChatResponse:
    return ChatResponse(
        id=str(chat.id),
        title=chat.title,
        document_id=str(chat.document_id) if chat.document_id else None,
        messages=[
            ChatMessageResponse(
                id=str(m.id),
                role=m.role,
                content=m.content,
                metadata=m.metadata,
                created_at=m.created_at,
            )
            for m in chat.messages
        ],
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )


def _map_summary(chat: ChatAggregate) -> ChatSummary:
    last_preview = ""
    if chat.messages:
        last_preview = chat.messages[-1].content[:80]
    return ChatSummary(
        id=str(chat.id),
        title=chat.title,
        document_id=str(chat.document_id) if chat.document_id else None,
        message_count=len(chat.messages),
        last_message_preview=last_preview,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )


@router.get("/", response_model=ChatListResponse, summary="Listar mis chats")
async def list_chats(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    repo: Annotated[ChatRepository, Depends(get_chat_repo)],
):
    chats = await repo.find_by_owner(UUID(current_user_id))
    return ChatListResponse(chats=[_map_summary(c) for c in chats])


@router.post("/", response_model=ChatResponse, status_code=201, summary="Crear nuevo chat")
async def create_chat(
    body: ChatCreateRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    repo: Annotated[ChatRepository, Depends(get_chat_repo)],
):
    chat = ChatAggregate.create(
        owner_id=UUID(current_user_id),
        title=body.title,
        document_id=body.document_id,
    )
    await repo.save(chat)
    return _map_chat(chat)


@router.get("/{chat_id}", response_model=ChatResponse, summary="Obtener chat por id")
async def get_chat(
    chat_id: UUID,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    repo: Annotated[ChatRepository, Depends(get_chat_repo)],
):
    chat = await repo.find_by_id(chat_id)
    if chat is None or str(chat.owner_id) != current_user_id:
        raise HTTPException(status_code=404, detail=_MSG_NO_ENCONTRADO)
    return _map_chat(chat)


@router.put("/{chat_id}", response_model=ChatResponse, summary="Actualizar chat")
async def update_chat(
    chat_id: UUID,
    body: ChatCreateRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    repo: Annotated[ChatRepository, Depends(get_chat_repo)],
):
    chat = await repo.find_by_id(chat_id)
    if chat is None or str(chat.owner_id) != current_user_id:
        raise HTTPException(status_code=404, detail=_MSG_NO_ENCONTRADO)
    if body.title is not None:
        try:
            chat.set_title(body.title)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
    if body.document_id is not None:
        chat.link_document(body.document_id)
    await repo.save(chat)
    return _map_chat(chat)


@router.post("/{chat_id}/messages", response_model=ChatResponse, summary="Agregar mensaje")
async def add_message(
    chat_id: UUID,
    body: ChatAddMessageRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    repo: Annotated[ChatRepository, Depends(get_chat_repo)],
    tutor: Annotated[ChatTutorService, Depends(get_chat_tutor_service)],
):
    chat = await repo.find_by_id(chat_id)
    if chat is None or str(chat.owner_id) != current_user_id:
        raise HTTPException(status_code=404, detail=_MSG_NO_ENCONTRADO)
    try:
        chat.add_message(role=body.role, content=body.content, metadata=body.metadata)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if body.role == "user":
        try:
            answer = await tutor.answer(
                document_id=chat.document_id,
                question=body.content,
                student_id=UUID(current_user_id),
            )
            chat.add_message(
                role="assistant",
                content=answer,
                metadata={"source": "tutor"},
            )
        except Exception:
            chat.add_message(
                role="system",
                content="Lo siento, no pude generar una respuesta en este momento. Intenta de nuevo.",
                metadata={"source": "error"},
            )

    await repo.save(chat)
    return _map_chat(chat)


@router.delete("/{chat_id}", status_code=204, summary="Eliminar chat")
async def delete_chat(
    chat_id: UUID,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    repo: Annotated[ChatRepository, Depends(get_chat_repo)],
):
    chat = await repo.find_by_id(chat_id)
    if chat is None or str(chat.owner_id) != current_user_id:
        raise HTTPException(status_code=404, detail=_MSG_NO_ENCONTRADO)
    await repo.delete(chat_id)
