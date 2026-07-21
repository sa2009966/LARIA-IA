from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class QuizQuestionPublicDTO:
    index: int
    text: str
    options: dict[str, str]
    difficulty: str


@dataclass
class QuizPublicDTO:
    id: UUID
    document_id: UUID
    questions: list[QuizQuestionPublicDTO]
    total_points: int
    created_at: datetime


@dataclass
class AttemptQuestionResultDTO:
    index: int
    text: str
    selected: str | None
    correct_answer: str
    is_correct: bool


@dataclass
class QuizAttemptResultDTO:
    attempt_id: UUID
    quiz_id: UUID
    document_id: UUID
    score: int
    total_points: int
    questions: list[AttemptQuestionResultDTO]
    completed_at: datetime


@dataclass
class QuizAttemptSummaryDTO:
    attempt_id: UUID
    quiz_id: UUID
    document_id: UUID
    score: int
    total_points: int
    completed_at: datetime


@dataclass
class TutorInteractionSummaryDTO:
    id: UUID
    document_id: UUID
    question: str
    answer: str
    asked_at: datetime


@dataclass
class LearningHistoryDTO:
    attempts: list[QuizAttemptSummaryDTO] = field(default_factory=list)
    tutor_interactions: list[TutorInteractionSummaryDTO] = field(default_factory=list)
