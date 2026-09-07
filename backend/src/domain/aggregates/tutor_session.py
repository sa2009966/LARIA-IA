"""Sesión pedagógica multi-turno por estudiante y documento."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionStep(str, Enum):
    INTRODUCE = "introduce"
    HINT = "hint"
    PRACTICE = "practice"
    CHECK = "check"


@dataclass
class TutorSession:
    id: UUID = field(default_factory=uuid4)
    student_id: UUID = field(default_factory=uuid4)
    document_id: UUID = field(default_factory=uuid4)
    step: SessionStep = SessionStep.INTRODUCE
    objective: str = ""
    focus_concepts: list[str] = field(default_factory=list)
    hints_given: list[str] = field(default_factory=list)
    turns: int = 0
    updated_at: datetime = field(default_factory=_utc_now)
    version: int = 0

    @staticmethod
    def start(
        student_id: UUID,
        document_id: UUID,
        objective: str = "",
        focus_concepts: tuple[str, ...] = (),
    ) -> "TutorSession":
        return TutorSession(
            student_id=student_id,
            document_id=document_id,
            step=SessionStep.INTRODUCE,
            objective=objective,
            focus_concepts=list(focus_concepts),
        )

    def record_ask(self, hint_summary: str = "", focus: tuple[str, ...] = ()) -> None:
        self.turns += 1
        if focus:
            for c in focus:
                if c and c not in self.focus_concepts:
                    self.focus_concepts.append(c)
            self.focus_concepts = self.focus_concepts[:8]
        if hint_summary:
            self.hints_given.append(hint_summary[:200])
            self.hints_given = self.hints_given[-10:]
        if self.step == SessionStep.INTRODUCE:
            self.step = SessionStep.HINT
        elif self.step == SessionStep.HINT and self.turns >= 2:
            self.step = SessionStep.PRACTICE
        self.updated_at = _utc_now()

    def record_quiz_check(self, score_ratio: float) -> None:
        self.turns += 1
        self.step = SessionStep.CHECK
        if score_ratio < 0.5:
            self.step = SessionStep.HINT
        elif score_ratio < 0.8:
            self.step = SessionStep.PRACTICE
        else:
            self.step = SessionStep.INTRODUCE
            self.hints_given.clear()
        self.updated_at = _utc_now()
