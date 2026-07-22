from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class DocumentMastery:
    """Dominio estimado de un documento a partir de intentos y señales ask."""

    document_id: UUID
    attempts: int = 0
    mastery: float = 0.0  # [0, 1] media móvil exponencial
    last_score_ratio: float = 0.0
    incorrect_streak: int = 0
    struggle_signals: int = 0

    def apply_result(self, score_ratio: float, alpha: float = 0.4) -> None:
        ratio = max(0.0, min(1.0, float(score_ratio)))
        self.attempts += 1
        self.last_score_ratio = ratio
        if self.attempts == 1:
            self.mastery = ratio
        else:
            self.mastery = (alpha * ratio) + ((1.0 - alpha) * self.mastery)
        if ratio < 0.5:
            self.incorrect_streak += 1
        else:
            self.incorrect_streak = 0

    def apply_soft_struggle(self, pull_toward: float = 0.2, weight: float = 0.5) -> None:
        """Ajuste suave por señal de ask (no cuenta como intento de quiz)."""
        target = max(0.0, min(1.0, pull_toward))
        w = max(0.0, min(1.0, weight))
        self.mastery = (w * target) + ((1.0 - w) * self.mastery)
        self.struggle_signals += 1
        self.last_score_ratio = min(self.last_score_ratio, target)


@dataclass
class StudentProfile:
    """Perfil cognitivo derivado de evidencia (quiz + señales de ask)."""

    student_id: UUID
    mastery_by_document: dict[UUID, DocumentMastery] = field(default_factory=dict)
    frequent_errors: list[str] = field(default_factory=list)
    pace: str = "steady"  # slow | steady | fast
    total_attempts: int = 0
    total_struggle_signals: int = 0
    updated_at: datetime = field(default_factory=_utc_now)

    @staticmethod
    def create(student_id: UUID) -> "StudentProfile":
        return StudentProfile(student_id=student_id)

    def mastery_for(self, document_id: UUID) -> float:
        entry = self.mastery_by_document.get(document_id)
        return entry.mastery if entry else 0.0

    def record_quiz_result(
        self,
        document_id: UUID,
        score_ratio: float,
        missed_concepts: tuple[str, ...] = (),
    ) -> None:
        entry = self.mastery_by_document.get(document_id)
        if entry is None:
            entry = DocumentMastery(document_id=document_id)
            self.mastery_by_document[document_id] = entry
        entry.apply_result(score_ratio)
        self.total_attempts += 1
        self._push_errors(missed_concepts)
        self._update_pace()
        self.updated_at = _utc_now()

    def record_ask_struggle(
        self,
        document_id: UUID,
        strength: float = 0.7,
        concepts: tuple[str, ...] = (),
    ) -> None:
        """Incorpora auto-reporte/confusión del /ask antes de decidir estrategia."""
        entry = self.mastery_by_document.get(document_id)
        if entry is None:
            entry = DocumentMastery(document_id=document_id)
            self.mastery_by_document[document_id] = entry
        pull = 0.15 + (0.25 * max(0.0, min(1.0, strength)))
        weight = 0.35 + (0.35 * max(0.0, min(1.0, strength)))
        entry.apply_soft_struggle(pull_toward=pull, weight=weight)
        self.total_struggle_signals += 1
        self._push_errors(concepts)
        if entry.mastery < 0.4:
            self.pace = "slow"
        self.updated_at = _utc_now()

    def clear_document(self, document_id: UUID) -> None:
        self.mastery_by_document.pop(document_id, None)
        self.updated_at = _utc_now()

    def _push_errors(self, concepts: tuple[str, ...]) -> None:
        for concept in concepts:
            label = concept.strip()
            if not label:
                continue
            if label in self.frequent_errors:
                self.frequent_errors.remove(label)
            self.frequent_errors.insert(0, label)
        self.frequent_errors = self.frequent_errors[:20]

    def _update_pace(self) -> None:
        if self.total_attempts <= 1 and self.total_struggle_signals == 0:
            self.pace = "steady"
            return
        weak = sum(1 for m in self.mastery_by_document.values() if m.mastery < 0.4)
        strong = sum(1 for m in self.mastery_by_document.values() if m.mastery >= 0.7)
        if weak > strong:
            self.pace = "slow"
        elif strong > weak and self.total_attempts >= 3:
            self.pace = "fast"
        else:
            self.pace = "steady"

    def weakest_documents(self, limit: int = 3) -> list[UUID]:
        ranked = sorted(
            self.mastery_by_document.values(),
            key=lambda m: (m.mastery, -m.attempts),
        )
        return [m.document_id for m in ranked[:limit]]
