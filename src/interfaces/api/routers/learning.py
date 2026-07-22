from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from src.application.services.quiz_service import QuizService
from src.interfaces.api.dependencies import get_current_user_id, get_quiz_service
from src.interfaces.api.openapi_responses import RESP_401_UNAUTHORIZED
from src.interfaces.schemas.quiz_schemas import (
    DocumentMasteryItem,
    LearningHistoryResponse,
    LearningRecommendationItem,
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
    service: Annotated[QuizService, Depends(get_quiz_service)],
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
            )
            for r in history.recommendations
        ],
    )


@router.get(
    "/me/profile",
    response_model=StudentProfileResponse,
    summary="Perfil cognitivo del estudiante",
    description=(
        "Solo lectura del perfil derivado de evidencia (mastery por documento, ritmo, errores)."
    ),
    responses={
        **RESP_401_UNAUTHORIZED,
    },
)
async def get_my_profile(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[QuizService, Depends(get_quiz_service)],
):
    profile = await service.get_profile(UUID(current_user_id))
    return StudentProfileResponse(
        student_id=str(profile.student_id),
        pace=profile.pace,
        total_attempts=profile.total_attempts,
        total_struggle_signals=profile.total_struggle_signals,
        frequent_errors=list(profile.frequent_errors),
        updated_at=profile.updated_at,
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
    )
