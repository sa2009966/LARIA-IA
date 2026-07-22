from dataclasses import dataclass, field
from enum import Enum


class Difficulty(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class BloomLevel(Enum):
    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"


@dataclass(frozen=True)
class Question:
    text: str
    difficulty: Difficulty = Difficulty.EASY
    bloom_level: BloomLevel = BloomLevel.REMEMBER

    def __post_init__(self):
        if not self.text or len(self.text.strip()) == 0:
            raise ValueError("Question text cannot be empty")
        if len(self.text) > 4000:
            raise ValueError("Question text cannot exceed 4000 characters")


@dataclass(frozen=True)
class QuizQuestion:
    text: str
    options: dict[str, str]  # {"A": "option", "B": "option", ...}
    correct_answer: str
    difficulty: Difficulty = Difficulty.MEDIUM

    def __post_init__(self):
        if not self.text or len(self.text.strip()) == 0:
            raise ValueError("Question text cannot be empty")
        if len(self.options) < 2:
            raise ValueError("Quiz question must have at least 2 options")
        if self.correct_answer not in self.options:
            raise ValueError(f"Correct answer '{self.correct_answer}' not in options")
        for key in self.options:
            if len(key) != 1:
                raise ValueError(f"Option keys must be single characters: {key}")


@dataclass(frozen=True)
class Quiz:
    questions: list[QuizQuestion] = field(default_factory=list)

    @property
    def total_points(self) -> int:
        return len(self.questions) * 10

    @property
    def total_questions(self) -> int:
        return len(self.questions)
