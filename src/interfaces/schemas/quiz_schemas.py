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


class LearningRecommendationItem(BaseModel):
    kind: str
    message: str
    document_id: str | None = None


class LearningHistoryResponse(BaseModel):
    attempts: list[QuizAttemptSummaryItem]
    tutor_interactions: list[TutorInteractionSummaryItem]
    recommendations: list[LearningRecommendationItem] = []


class DocumentMasteryItem(BaseModel):
    document_id: str
    attempts: int
    mastery: float
    last_score_ratio: float
    struggle_signals: int = 0


class StudentProfileResponse(BaseModel):
    student_id: str
    pace: str
    total_attempts: int
    frequent_errors: list[str]
    updated_at: datetime
    mastery_by_document: list[DocumentMasteryItem]
    total_struggle_signals: int = 0
