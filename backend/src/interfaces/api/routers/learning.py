from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.services.learning_query_service import LearningQueryService
from src.domain.aggregates.learning_path import LearningPathAggregate
from src.domain.ports.repositories import (
    LearningPathRepository,
    StudentProfileRepository,
)
from src.interfaces.api.dependencies import (
    get_current_user_id,
    get_learning_path_repo,
    get_learning_query_service,
    get_profile_repo,
)
from src.interfaces.api.openapi_responses import RESP_401_UNAUTHORIZED
from src.interfaces.schemas.learning_path_schemas import (
    LearningModuleResponse,
    LearningPathCreateRequest,
    LearningPathListResponse,
    LearningPathResponse,
)
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

_MSG_NO_ENCONTRADO = "Ruta de aprendizaje no encontrada"


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
                document_id=str(a.document_id) if a.document_id else None,
                score=a.score,
                total_points=a.total_points,
                completed_at=a.completed_at,
            )
            for a in history.attempts
        ],
        tutor_interactions=[
            TutorInteractionSummaryItem(
                id=str(i.id),
                document_id=str(i.document_id) if i.document_id else None,
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
        level_by_topic=dict(profile.level_by_topic),
        topic_labels=dict(profile.topic_labels),
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


def _map_module(m) -> LearningModuleResponse:
    diff = m.difficulty.value if hasattr(m.difficulty, "value") else str(m.difficulty)
    return LearningModuleResponse(
        id=str(m.id),
        title=m.title,
        concept=m.concept,
        difficulty=diff,
        prerequisites=list(m.prerequisites),
        status=m.status,
        mastery=m.mastery,
        position=m.position,
    )


async def _projected(
    path: LearningPathAggregate,
    profile_repo: StudentProfileRepository,
    student_id: UUID,
) -> LearningPathAggregate:
    """Proyecta el mastery del perfil sobre la ruta antes de devolverla.

    El progreso se deriva de la evidencia en cada lectura y no se persiste:
    guardar la proyección volvería a crear dos verdades que hay que mantener
    sincronizadas (ADR-008). La decisión de qué es el mastery sigue estando en
    el dominio; aquí solo se le pasan los números del perfil.
    """
    profile = await profile_repo.find_by_student(student_id)
    path.project_mastery(profile.effective_mastery_by_concept() if profile else {})
    return path


def _map_path(p: LearningPathAggregate) -> LearningPathResponse:
    return LearningPathResponse(
        id=str(p.id),
        subject=p.subject,
        title=p.title,
        modules=[_map_module(m) for m in p.modules],
        progress=p.progress,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get(
    "/paths",
    response_model=LearningPathListResponse,
    summary="Listar rutas de aprendizaje",
    responses={**RESP_401_UNAUTHORIZED},
)
async def list_learning_paths(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    repo: Annotated[LearningPathRepository, Depends(get_learning_path_repo)],
    profile_repo: Annotated[StudentProfileRepository, Depends(get_profile_repo)],
):
    owner = UUID(current_user_id)
    paths = await repo.find_by_owner(owner)
    return LearningPathListResponse(
        paths=[_map_path(await _projected(p, profile_repo, owner)) for p in paths]
    )


@router.post(
    "/paths",
    response_model=LearningPathResponse,
    status_code=201,
    summary="Crear ruta de aprendizaje",
    responses={**RESP_401_UNAUTHORIZED},
)
async def create_learning_path(
    body: LearningPathCreateRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    repo: Annotated[LearningPathRepository, Depends(get_learning_path_repo)],
    profile_repo: Annotated[StudentProfileRepository, Depends(get_profile_repo)],
):
    path = LearningPathAggregate.create(
        owner_id=UUID(current_user_id),
        subject=body.subject,
        title=body.title,
        modules=[
            {
                "title": m.title,
                "concept": m.concept,
                "difficulty": m.difficulty,
                "prerequisites": m.prerequisites,
            }
            for m in body.modules
        ],
    )
    await repo.save(path)
    return _map_path(await _projected(path, profile_repo, UUID(current_user_id)))


@router.get(
    "/paths/{path_id}",
    response_model=LearningPathResponse,
    summary="Obtener ruta de aprendizaje",
    responses={**RESP_401_UNAUTHORIZED},
)
async def get_learning_path(
    path_id: UUID,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    repo: Annotated[LearningPathRepository, Depends(get_learning_path_repo)],
    profile_repo: Annotated[StudentProfileRepository, Depends(get_profile_repo)],
):
    owner = UUID(current_user_id)
    path = await repo.find_by_id(path_id)
    if path is None or not path.is_owned_by(owner):
        raise HTTPException(status_code=404, detail=_MSG_NO_ENCONTRADO)
    return _map_path(await _projected(path, profile_repo, owner))


# No hay endpoint para escribir el mastery de un módulo, a propósito: el
# progreso se gana con evidencia (quizzes, tutoría), no se declara por HTTP
# (ADR-008).


@router.delete(
    "/paths/{path_id}",
    status_code=204,
    summary="Eliminar ruta de aprendizaje",
    responses={**RESP_401_UNAUTHORIZED},
)
async def delete_learning_path(
    path_id: UUID,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    repo: Annotated[LearningPathRepository, Depends(get_learning_path_repo)],
):
    path = await repo.find_by_id(path_id)
    if path is None or not path.is_owned_by(UUID(current_user_id)):
        raise HTTPException(status_code=404, detail=_MSG_NO_ENCONTRADO)
    await repo.delete(path_id)
