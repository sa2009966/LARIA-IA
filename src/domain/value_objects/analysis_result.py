from dataclasses import dataclass, field


@dataclass(frozen=True)
class AnalysisResult:
    """Resultado de análisis pedagógico de un documento.

    Forma canónica alineada con la API y el adaptador de IA:
    conceptos y preguntas sugeridas como listas de strings.
    """

    summary: str
    key_concepts: list[str] = field(default_factory=list)
    suggested_questions: list[str] = field(default_factory=list)
    confidence_score: float = 0.0

    def __post_init__(self):
        if not self.summary or len(self.summary.strip()) == 0:
            raise ValueError("Summary cannot be empty")
        if len(self.summary) > 10000:
            raise ValueError("Summary exceeds 10000 characters")
        if self.confidence_score < 0 or self.confidence_score > 1:
            raise ValueError(f"Confidence score must be between 0 and 1: {self.confidence_score}")
        object.__setattr__(self, "key_concepts", [str(c) for c in self.key_concepts])
        object.__setattr__(self, "suggested_questions", [str(q) for q in self.suggested_questions])

    @property
    def sorted_concepts(self) -> list[str]:
        return list(self.key_concepts)
