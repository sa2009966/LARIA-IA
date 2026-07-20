from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class QuestionDTO:
    text: str
    difficulty: str = "easy"
    bloom_level: str = "remember"


@dataclass
class AnalysisDTO:
    document_id: UUID
    summary: str
    key_concepts: list[str] = field(default_factory=list)
    suggested_questions: list[QuestionDTO] = field(default_factory=list)
    model_used: str = ""


@dataclass
class QuizQuestionDTO:
    text: str
    options: dict[str, str]
    correct_answer: str
    difficulty: str = "medium"


@dataclass
class QuizDTO:
    questions: list[QuizQuestionDTO] = field(default_factory=list)
    total_points: int = 0
