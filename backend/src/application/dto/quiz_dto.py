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
    concept: str | None = None
    priority: float = 0.0
    suggested_minutes: int | None = None


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
class ConceptMasteryDTO:
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


@dataclass
class PedagogicalMemoryDTO:
    frequent_misconceptions: list[str] = field(default_factory=list)
    successful_examples: list[str] = field(default_factory=list)
    successful_analogies: list[str] = field(default_factory=list)
    preferred_explanation_style: str = "simple"
    last_effective_strategies: list[str] = field(default_factory=list)


@dataclass
class StudentProfileDTO:
    student_id: UUID
    pace: str
    total_attempts: int
    frequent_errors: list[str]
    updated_at: datetime
    mastery_by_document: list[DocumentMasteryDTO] = field(default_factory=list)
    mastery_by_concept: list[ConceptMasteryDTO] = field(default_factory=list)
    total_struggle_signals: int = 0
    learning_velocity: float = 0.0
    pedagogical_memory: PedagogicalMemoryDTO | None = None
