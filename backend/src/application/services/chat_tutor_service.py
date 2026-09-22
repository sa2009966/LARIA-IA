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
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.services.adaptive_policy import AdaptationParameters
from src.domain.services.affect_policy import AffectPolicy
from src.domain.services.intent_detector import IntentDetector, TutorIntent
from src.domain.services.pedagogical_engine import (
    PedagogicalDecision,
    PedagogicalMode,
)
from src.domain.services.prerequisite_graph import GateAction
from src.domain.services.response_envelope import (
    EnvelopeType,
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


def _is_remediation(decision: Optional[PedagogicalDecision]) -> bool:
    """Si el turno está remediando, no es momento de celebrar nada."""
    if decision is None:
        return False
    return (
        decision.mode == PedagogicalMode.SCAFFOLD
        or decision.gate_action == GateAction.SEQUENCE
    )


def _milestone(
    profile: Optional[StudentProfile], decision: Optional[PedagogicalDecision]
) -> Optional[str]:
    """Concepto dominado y aún no reconocido, si el turno admite celebrarlo.

    El canal positivo existía y estaba muerto: ningún modo mapeaba a
    `celebration` y nadie pasaba `last_score_ratio`, así que `CELEBRATORY` era
    inalcanzable. Hacer visible lo logrado es el P4 del plan (ADR-009).
    """
    if profile is None or _is_remediation(decision):
        return None
    return profile.pending_celebration()


def _last_graded_ratio(
    profile: Optional[StudentProfile],
    document_id: Optional[UUID],
    decision: Optional[PedagogicalDecision],
) -> Optional[float]:
    """Último acierto **calificado** del documento, si el turno admite tono alto.

    Exige `attempts > 0`: un documento sin quizzes tiene `last_score_ratio`
    en 0.0 por defecto y leerlo sería inventar un mal resultado (ADR-007).
    """
    if profile is None or document_id is None or _is_remediation(decision):
        return None
    entry = profile.mastery_by_document.get(document_id)
    if entry is None or entry.attempts == 0:
        return None
    return entry.last_score_ratio


def _envelope_type(
    decision: Optional[PedagogicalDecision], milestone: Optional[str]
) -> EnvelopeType:
    if milestone:
        return "celebration"
    return envelope_type_for_mode(decision.mode if decision else None)


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
            decision = plan.decision
            milestone = _milestone(profile, decision)
            await self._analyze_service.finalize_interaction(
                plan, content, celebrated_concept=milestone
            )
            affect = self._affect.select(
                profile,
                decision,
                last_score_ratio=_last_graded_ratio(profile, document_id, decision),
            )
            extra = {
                "intent": intention.intent.value,
                # La tutoría adaptativa exige material: con documento el turno
                # pasa por el motor; sin él es conversación y no promete más.
                # La UI necesita poder decirlo en vez de aparentar tutoría.
                "grounded": True,
                **_control_flow_payload(plan.adaptation),
            }
            if milestone:
                extra["celebrated_concept"] = milestone
            if plan.explanation:
                extra["explanation"] = plan.explanation
            envelope = ResponseEnvelope.from_decision(
                decision,
                _envelope_type(decision, milestone),
                affect,
                content=content,
                extra=extra,
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
            extra={"intent": intention.intent.value, "grounded": False},
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
        extra: dict = {
            "intent": intention.intent.value,
            "grounded": document_id is not None,
        }
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
            milestone = _milestone(profile, plan.decision)
            await self._analyze_service.finalize_interaction(
                plan, content, celebrated_concept=milestone
            )

            extra.update(_control_flow_payload(plan.adaptation))
            if milestone:
                extra["celebrated_concept"] = milestone
            if plan.explanation:
                extra["explanation"] = plan.explanation
            envelope = ResponseEnvelope.from_decision(
                plan.decision,
                _envelope_type(plan.decision, milestone),
                self._affect.select(
                    profile,
                    plan.decision,
                    last_score_ratio=_last_graded_ratio(
                        profile, document_id, plan.decision
                    ),
                ),
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
