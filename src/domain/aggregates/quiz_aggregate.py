from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.domain.events.domain_events import DomainEvent, QuizGeneratedEvent
from src.domain.value_objects.question import Difficulty, QuizQuestion


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_difficulty(value) -> Difficulty:
    if isinstance(value, Difficulty):
        return value
    return Difficulty(str(value).lower())


@dataclass(frozen=True)
class QuizGrade:
    """Resultado de calificar un intento: evidencia de aprendizaje por pregunta."""

    per_question_correct: tuple[bool, ...]
    score: int
    total_points: int

    @property
    def correct_count(self) -> int:
        return sum(1 for c in self.per_question_correct if c)


@dataclass
class QuizAggregate:
    id: UUID = field(default_factory=uuid4)
    document_id: UUID = field(default_factory=uuid4)
    owner_id: UUID = field(default_factory=uuid4)
    questions: list[QuizQuestion] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utc_now)
    events: list[DomainEvent] = field(default_factory=list)

    @staticmethod
    def create(
        document_id: UUID,
        owner_id: UUID,
        questions: list[QuizQuestion],
    ) -> "QuizAggregate":
        if not questions:
            raise ValueError("Un quiz debe tener al menos una pregunta")
        normalized: list[QuizQuestion] = []
        for q in questions:
            normalized.append(
                QuizQuestion(
                    text=q.text,
                    options=dict(q.options),
                    correct_answer=q.correct_answer,
                    difficulty=_normalize_difficulty(q.difficulty),
                )
            )
        quiz = QuizAggregate(
            document_id=document_id,
            owner_id=owner_id,
            questions=normalized,
        )
        quiz.events.append(
            QuizGeneratedEvent(
                aggregate_id=quiz.id,
                document_id=document_id,
                owner_id=owner_id,
                num_questions=len(normalized),
            )
        )
        return quiz

    @property
    def total_points(self) -> int:
        return len(self.questions) * 10

    def is_owned_by(self, user_id: UUID) -> bool:
        return self.owner_id == user_id

    def grade(self, answers: dict[int, str]) -> QuizGrade:
        """Califica un intento completo. Requiere respuesta para cada pregunta."""
        n = len(self.questions)
        if len(answers) != n or any(i not in answers for i in range(n)):
            raise ValueError(
                f"Debes responder las {n} preguntas del cuestionario (intento incompleto)."
            )
        for index, choice in answers.items():
            if index < 0 or index >= n:
                raise ValueError(f"Índice de pregunta inválido: {index}")
            if choice not in self.questions[index].options:
                raise ValueError(
                    f"Opción '{choice}' no válida para la pregunta {index}"
                )

        per_question = tuple(
            answers[i] == self.questions[i].correct_answer for i in range(n)
        )
        correct = sum(1 for c in per_question if c)
        return QuizGrade(
            per_question_correct=per_question,
            score=correct * 10,
            total_points=self.total_points,
        )

    def clear_events(self) -> None:
        self.events.clear()
