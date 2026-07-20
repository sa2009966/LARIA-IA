from dataclasses import dataclass, field
from src.domain.value_objects.question import Question


@dataclass(frozen=True)
class AnalysisResult:
    summary: str
    key_concepts: list[tuple[str, float]] = field(default_factory=list)
    suggested_questions: list[Question] = field(default_factory=list)
    confidence_score: float = 0.0

    def __post_init__(self):
        if not self.summary or len(self.summary.strip()) == 0:
            raise ValueError("Summary cannot be empty")
        if len(self.summary) > 10000:
            raise ValueError("Summary exceeds 10000 characters")
        if self.confidence_score < 0 or self.confidence_score > 1:
            raise ValueError(f"Confidence score must be between 0 and 1: {self.confidence_score}")

    @property
    def sorted_concepts(self) -> list[str]:
        return [concept for concept, _ in sorted(self.key_concepts, key=lambda x: x[1], reverse=True)]
