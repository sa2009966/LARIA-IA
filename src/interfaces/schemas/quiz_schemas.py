from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field


class QuizQuestionPublicItem(BaseModel):
    index: int
    text: str
    options: dict[str, str]
    difficulty: str = "medium"


class QuizPublicResponse(BaseModel):
    id: str
    document_id: str
    questions: list[QuizQuestionPublicItem]
    total_points: int
    created_at: datetime


class QuizAttemptRequest(BaseModel):
    answers: Annotated[
        dict[str, str],
        Field(
            min_length=1,
            description="Mapa índice-de-pregunta (como string) → opción elegida, p. ej. {\"0\": \"A\"}",
        ),
    ]


class AttemptQuestionResultItem(BaseModel):
    index: int
    text: str
    selected: str | None
    correct_answer: str
    is_correct: bool


class QuizAttemptResponse(BaseModel):
    attempt_id: str
    quiz_id: str
    document_id: str
    score: int
    total_points: int
    questions: list[AttemptQuestionResultItem]
    completed_at: datetime


class QuizAttemptSummaryItem(BaseModel):
    attempt_id: str
    quiz_id: str
    document_id: str
    score: int
    total_points: int
    completed_at: datetime


class TutorInteractionSummaryItem(BaseModel):
    id: str
    document_id: str
    question: str
    answer: str
    asked_at: datetime


class LearningHistoryResponse(BaseModel):
    attempts: list[QuizAttemptSummaryItem]
    tutor_interactions: list[TutorInteractionSummaryItem]
