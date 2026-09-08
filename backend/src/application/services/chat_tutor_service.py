"""Servicio de tutoría para chats: orquesta el motor pedagógico o el modo libre."""
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from src.application.services.analyze_document_service import AnalyzeDocumentService
from src.application.services.llm_gate import LlmGate
from src.domain.ports.embodiment import AffectState
from src.domain.ports.repositories import (
    DocumentRepository,
    StudentProfileRepository,
)
from src.domain.services.affect_policy import AffectPolicy
from src.domain.services.intent_detector import IntentDetector, TutorIntent
from src.domain.services.pedagogical_engine import PedagogicalDecision
from src.domain.services.response_envelope import (
    ResponseEnvelope,
    envelope_type_for_mode,
)


@dataclass(frozen=True)
class TutorResponse:
    """Respuesta del tutor: texto + envelope para la UI (tipo/emoción/payload)."""

    content: str
    envelope: ResponseEnvelope


class ChatTutorService:
    """Responde mensajes de chat: usa el motor pedagógico si hay documento vinculado,
    o modo libre (LlmGate directo) si es conversación general."""

    def __init__(
        self,
        analyze_service: Optional[AnalyzeDocumentService] = None,
        llm_gate: Optional[LlmGate] = None,
        document_repository: Optional[DocumentRepository] = None,
        profile_repository: Optional[StudentProfileRepository] = None,
    ) -> None:
        self._analyze_service = analyze_service
        self._llm_gate = llm_gate
        self._doc_repo = document_repository
        self._profile_repo = profile_repository
        self._affect = AffectPolicy()
        self._intent = IntentDetector()

    async def answer(
        self,
        document_id: Optional[UUID],
        question: str,
        student_id: UUID,
    ) -> TutorResponse:
        """Devuelve la respuesta del tutor con su envelope de UI.

        Con document_id y ownership → motor pedagógico completo (decisión + emoción).
        Sin documento → modo libre (LlmGate, envelope genérico).
        """
        intention = self._intent.detect(question)
        profile = None
        if self._profile_repo is not None:
            profile = await self._profile_repo.find_by_student(student_id)

        if document_id is not None:
            if self._analyze_service is None:
                raise ValueError("Servicio de análisis no configurado para chats con documento")
            content, decision = await self._analyze_service.answer_question_with_pedagogy(
                document_id,
                question,
                student_id,
            )
            affect = self._affect.select(profile, decision)
            envelope_type = envelope_type_for_mode(decision.mode if decision else None)
            envelope = ResponseEnvelope.from_decision(
                decision,
                envelope_type,
                affect,
                content=content,
                extra={"intent": intention.intent.value},
            )
            return TutorResponse(content=content, envelope=envelope)

        if self._llm_gate is None:
            raise ValueError("LLM gate no configurado para chats libres")
        content = await self._llm_gate.answer_question(
            context="",
            question=question,
            decision=None,
        )
        affect = self._affect.select(profile, None)
        envelope = ResponseEnvelope.from_decision(
            None,
            "answer",
            affect,
            content=content,
            extra={"intent": intention.intent.value},
        )
        return TutorResponse(content=content, envelope=envelope)

    async def answer_stream(
        self,
        document_id: Optional[UUID],
        question: str,
        student_id: UUID,
    ):
        """Streaming de la respuesta del tutor (yield de trozos).

        Modo libre → streaming directo del LlmGate.
        Con documento → streaming del LlmGate (sin orquestación pedagógica
        completa en v1; la decisión completa se mantiene en el path no-stream).
        """
        if self._llm_gate is None:
            raise ValueError("LLM gate no configurado para streaming")
        intention = self._intent.detect(question)
        decision = None
        content = ""
        async for token in self._llm_gate.answer_question_stream(
            context="",
            question=question,
            decision=decision,
        ):
            content += token
            yield token, None

        # Envelope final (tras el streaming) para que el cliente cierre.
        envelope = ResponseEnvelope.from_decision(
            decision,
            "answer",
            AffectState.ENCOURAGING,
            content=content,
            extra={"intent": intention.intent.value},
        )
        yield content, envelope
