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
    concept: str | None = None
    priority: float = 0.0
    suggested_minutes: int | None = None


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


class ConceptMasteryItem(BaseModel):
    concept_key: str
    attempts: int
    mastery: float
    last_score_ratio: float
    effective_mastery: float = 0.0
    confidence: float = 0.0
    last_practiced_at: datetime | None = None
    subject: str | None = None
    help_requests: int = 0
    error_streak: int = 0


class PedagogicalMemoryItem(BaseModel):
    frequent_misconceptions: list[str] = []
    successful_examples: list[str] = []
    successful_analogies: list[str] = []
    preferred_explanation_style: str = "simple"
    last_effective_strategies: list[str] = []


class StudentProfileResponse(BaseModel):
    student_id: str
    pace: str
    total_attempts: int
    frequent_errors: list[str]
    updated_at: datetime
    mastery_by_document: list[DocumentMasteryItem]
    mastery_by_concept: list[ConceptMasteryItem] = []
    total_struggle_signals: int = 0
    learning_velocity: float = 0.0
    pedagogical_memory: PedagogicalMemoryItem | None = None
