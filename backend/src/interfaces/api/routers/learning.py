from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from src.application.services.learning_query_service import LearningQueryService
from src.interfaces.api.dependencies import get_current_user_id, get_learning_query_service
from src.interfaces.api.openapi_responses import RESP_401_UNAUTHORIZED
from src.interfaces.schemas.quiz_schemas import (
    ConceptMasteryItem,
    DocumentMasteryItem,
    LearningHistoryResponse,
    LearningRecommendationItem,
    PedagogicalMemoryItem,
    QuizAttemptSummaryItem,
    StudentProfileResponse,
    TutorInteractionSummaryItem,
)

router = APIRouter(prefix="/learning", tags=["Aprendizaje"])


@router.get(
    "/me",
    response_model=LearningHistoryResponse,
    summary="Historial de evidencia de aprendizaje",
    description=(
        "Devuelve intentos de quiz, interacciones con el tutor y recomendaciones "
        "derivadas del perfil cognitivo (sin auto-declaración)."
    ),
    responses={
        **RESP_401_UNAUTHORIZED,
    },
)
async def get_my_learning_history(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[LearningQueryService, Depends(get_learning_query_service)],
):
    history = await service.get_learning_history(UUID(current_user_id))
    return LearningHistoryResponse(
        attempts=[
            QuizAttemptSummaryItem(
                attempt_id=str(a.attempt_id),
                quiz_id=str(a.quiz_id),
                document_id=str(a.document_id),
                score=a.score,
                total_points=a.total_points,
                completed_at=a.completed_at,
            )
            for a in history.attempts
        ],
        tutor_interactions=[
            TutorInteractionSummaryItem(
                id=str(i.id),
                document_id=str(i.document_id),
                question=i.question,
                answer=i.answer,
                asked_at=i.asked_at,
            )
            for i in history.tutor_interactions
        ],
        recommendations=[
            LearningRecommendationItem(
                kind=r.kind,
                message=r.message,
                document_id=str(r.document_id) if r.document_id else None,
                concept=r.concept,
                priority=r.priority,
                suggested_minutes=r.suggested_minutes,
            )
            for r in history.recommendations
        ],
    )


@router.get(
    "/me/profile",
    response_model=StudentProfileResponse,
    summary="Perfil cognitivo del estudiante",
    description=(
        "Perfil derivado de evidencia multi-señal: mastery efectivo (con olvido), "
        "confianza, memoria pedagógica y ritmo."
    ),
    responses={
        **RESP_401_UNAUTHORIZED,
    },
)
async def get_my_profile(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[LearningQueryService, Depends(get_learning_query_service)],
):
    profile = await service.get_profile(UUID(current_user_id))
    mem = profile.pedagogical_memory
    return StudentProfileResponse(
        student_id=str(profile.student_id),
        pace=profile.pace,
        total_attempts=profile.total_attempts,
        total_struggle_signals=profile.total_struggle_signals,
        frequent_errors=list(profile.frequent_errors),
        updated_at=profile.updated_at,
        learning_velocity=profile.learning_velocity,
        pedagogical_memory=(
            PedagogicalMemoryItem(
                frequent_misconceptions=list(mem.frequent_misconceptions),
                successful_examples=list(mem.successful_examples),
                successful_analogies=list(mem.successful_analogies),
                preferred_explanation_style=mem.preferred_explanation_style,
                last_effective_strategies=list(mem.last_effective_strategies),
            )
            if mem
            else None
        ),
        mastery_by_document=[
            DocumentMasteryItem(
                document_id=str(m.document_id),
                attempts=m.attempts,
                mastery=m.mastery,
                last_score_ratio=m.last_score_ratio,
                struggle_signals=m.struggle_signals,
            )
            for m in profile.mastery_by_document
        ],
        mastery_by_concept=[
            ConceptMasteryItem(
                concept_key=c.concept_key,
                attempts=c.attempts,
                mastery=c.mastery,
                last_score_ratio=c.last_score_ratio,
                effective_mastery=c.effective_mastery,
                confidence=c.confidence,
                last_practiced_at=c.last_practiced_at,
                subject=c.subject,
                help_requests=c.help_requests,
                error_streak=c.error_streak,
            )
            for c in profile.mastery_by_concept
        ],
    )
