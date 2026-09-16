"""Servicio de tutoría para chats: orquesta el motor pedagógico o el modo libre."""
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from src.application.services.analyze_document_service import AnalyzeDocumentService
from src.application.services.llm_gate import LlmGate
from src.domain.ports.repositories import (
    DocumentRepository,
    StudentProfileRepository,
)
from src.domain.services.adaptive_policy import AdaptationParameters
from src.domain.services.affect_policy import AffectPolicy
from src.domain.services.intent_detector import IntentDetector, TutorIntent
from src.domain.services.pedagogical_engine import PedagogicalDecision
from src.domain.services.response_envelope import (
    ResponseEnvelope,
    envelope_type_for_mode,
)


def _control_flow_payload(adaptation: AdaptationParameters) -> dict:
    """Familia control-flow: orquestación, no prompt.

    Viaja en el envelope para que la UI aplique la misma orquestación con y sin
    streaming (ADR-004, Decisión 3).
    """
    return {
        "practice_before_advance": adaptation.control_flow.practice_before_advance,
        "chunk_explanation": adaptation.control_flow.chunk_explanation,
    }


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
            plan = await self._analyze_service.prepare_pedagogy(
                document_id, question, student_id
            )
            content = await self._analyze_service.answer_from_plan(plan)
            await self._analyze_service.finalize_interaction(plan, content)
            decision = plan.decision
            affect = self._affect.select(profile, decision)
            envelope_type = envelope_type_for_mode(decision.mode if decision else None)
            envelope = ResponseEnvelope.from_decision(
                decision,
                envelope_type,
                affect,
                content=content,
                extra={
                    "intent": intention.intent.value,
                    **_control_flow_payload(plan.adaptation),
                },
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

        Con documento → mismo plan pedagógico que el path no-streaming: la
        decisión y la adaptación prompt-shaping se fijan antes de abrir el
        stream (ADR-004, Decisión 3). Sin documento → modo libre.
        """
        if self._llm_gate is None:
            raise ValueError("LLM gate no configurado para streaming")
        intention = self._intent.detect(question)
        extra: dict = {"intent": intention.intent.value}
        profile = None
        if self._profile_repo is not None:
            profile = await self._profile_repo.find_by_student(student_id)

        if document_id is not None:
            if self._analyze_service is None:
                raise ValueError("Servicio de análisis no configurado para chats con documento")
            plan = await self._analyze_service.prepare_pedagogy(
                document_id, question, student_id
            )
            content = ""
            async for token in self._analyze_service.stream_from_plan(plan):
                content += token
                yield token, None
            await self._analyze_service.finalize_interaction(plan, content)

            extra.update(_control_flow_payload(plan.adaptation))
            envelope = ResponseEnvelope.from_decision(
                plan.decision,
                envelope_type_for_mode(plan.decision.mode),
                self._affect.select(profile, plan.decision),
                content=content,
                extra=extra,
            )
            yield content, envelope
            return

        content = ""
        async for token in self._llm_gate.answer_question_stream(
            context="",
            question=question,
            decision=None,
        ):
            content += token
            yield token, None

        # Envelope final (tras el streaming) para que el cliente cierre.
        envelope = ResponseEnvelope.from_decision(
            None,
            "answer",
            self._affect.select(profile, None),
            content=content,
            extra=extra,
        )
        yield content, envelope
