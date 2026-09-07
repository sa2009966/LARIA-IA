"""Servicio de tutoría para chats: orquesta el motor pedagógico o el modo libre."""
from typing import Optional
from uuid import UUID

from src.application.services.analyze_document_service import AnalyzeDocumentService
from src.application.services.llm_gate import LlmGate
from src.domain.ports.repositories import DocumentRepository


class ChatTutorService:
    """Responde mensajes de chat: usa el motor pedagógico si hay documento vinculado,
    o modo libre (LlmGate directo) si es conversación general."""

    def __init__(
        self,
        analyze_service: Optional[AnalyzeDocumentService] = None,
        llm_gate: Optional[LlmGate] = None,
        document_repository: Optional[DocumentRepository] = None,
    ) -> None:
        self._analyze_service = analyze_service
        self._llm_gate = llm_gate
        self._doc_repo = document_repository

    async def answer(
        self,
        document_id: Optional[UUID],
        question: str,
        student_id: UUID,
    ) -> str:
        """Devuelve la respuesta del tutor.

        Si hay document_id y el usuario es dueño → motor pedagógico completo.
        Si no → modo libre: LlmGate.answer_question sin contexto de documento.
        """
        if document_id is not None:
            if self._analyze_service is None:
                raise ValueError("Servicio de análisis no configurado para chats con documento")
            return await self._analyze_service.answer_question(
                document_id,
                question,
                student_id,
            )

        if self._llm_gate is None:
            raise ValueError("LLM gate no configurado para chats libres")
        return await self._llm_gate.answer_question(
            context="",
            question=question,
            decision=None,
        )
