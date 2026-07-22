from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.services.quiz_service import QuizService
from src.domain.ports.ia_analyst import IAAnalysisError
from src.interfaces.api.dependencies import get_current_user_id, get_quiz_service
from src.interfaces.api.openapi_responses import (
    RESP_401_UNAUTHORIZED,
    RESP_404_NOT_FOUND,
    RESP_422_VALIDATION,
)
from src.interfaces.api.quiz_mappers import quiz_to_public_response
from src.interfaces.schemas.quiz_schemas import (
    AttemptQuestionResultItem,
    QuizAttemptRequest,
    QuizAttemptResponse,
    QuizPublicResponse,
)

router = APIRouter(prefix="/quizzes", tags=["Cuestionarios"])

_MSG_NO_ENCONTRADO = "Recurso no encontrado"


@router.get(
    "/{quiz_id}",
    response_model=QuizPublicResponse,
    summary="Obtener quiz propio (sin respuestas correctas)",
    description="Devuelve el cuestionario para reintento. No incluye `correct_answer`.",
    responses={
        **RESP_401_UNAUTHORIZED,
        **RESP_404_NOT_FOUND,
    },
)
async def get_quiz(
    quiz_id: str,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[QuizService, Depends(get_quiz_service)],
):
    try:
        quiz = await service.get_quiz(UUID(quiz_id), UUID(current_user_id))
    except (ValueError, PermissionError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_MSG_NO_ENCONTRADO)
    return quiz_to_public_response(quiz)


@router.post(
    "/{quiz_id}/attempts",
    response_model=QuizAttemptResponse,
    summary="Enviar intento de quiz",
    description=(
        "Califica en el servidor las respuestas del estudiante. "
        "Body: `{\"answers\": {\"0\": \"A\", \"1\": \"C\"}}`. "
        "La respuesta incluye corrección detallada y las respuestas correctas."
    ),
    responses={
        **RESP_401_UNAUTHORIZED,
        **RESP_404_NOT_FOUND,
        **RESP_422_VALIDATION,
    },
)
async def submit_attempt(
    quiz_id: str,
    body: QuizAttemptRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[QuizService, Depends(get_quiz_service)],
):
    try:
        answers = {int(k): v for k, v in body.answers.items()}
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Las claves de `answers` deben ser índices numéricos de pregunta.",
        )
    try:
        result = await service.submit_attempt(UUID(quiz_id), UUID(current_user_id), answers)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_MSG_NO_ENCONTRADO)
    except ValueError as exc:
        detail = str(exc)
        code = (
            status.HTTP_404_NOT_FOUND
            if "no encontrado" in detail.lower() or "Quiz no encontrado" in detail
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise HTTPException(
            status_code=code,
            detail=_MSG_NO_ENCONTRADO if code == status.HTTP_404_NOT_FOUND else detail,
        )
    except IAAnalysisError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return QuizAttemptResponse(
        attempt_id=str(result.attempt_id),
        quiz_id=str(result.quiz_id),
        document_id=str(result.document_id),
        score=result.score,
        total_points=result.total_points,
        questions=[
            AttemptQuestionResultItem(
                index=q.index,
                text=q.text,
                selected=q.selected,
                correct_answer=q.correct_answer,
                is_correct=q.is_correct,
            )
            for q in result.questions
        ],
        completed_at=result.completed_at,
    )
