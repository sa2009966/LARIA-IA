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
class LearningRecommendationDTO:
    kind: str
    message: str
    document_id: UUID | None = None


@dataclass
class LearningHistoryDTO:
    attempts: list[QuizAttemptSummaryDTO] = field(default_factory=list)
    tutor_interactions: list[TutorInteractionSummaryDTO] = field(default_factory=list)
    recommendations: list[LearningRecommendationDTO] = field(default_factory=list)


@dataclass
class DocumentMasteryDTO:
    document_id: UUID
    attempts: int
    mastery: float
    last_score_ratio: float
    struggle_signals: int = 0


@dataclass
class StudentProfileDTO:
    student_id: UUID
    pace: str
    total_attempts: int
    frequent_errors: list[str]
    updated_at: datetime
    mastery_by_document: list[DocumentMasteryDTO] = field(default_factory=list)
    total_struggle_signals: int = 0
