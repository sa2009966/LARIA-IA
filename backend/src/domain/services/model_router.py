"""Router de modelos OpenAI: mini por defecto, fuerte solo si justifica."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.domain.services.pedagogical_engine import PedagogicalDecision, PedagogicalMode


class LlmTask(str, Enum):
    ANALYZE = "analyze"
    ASK = "ask"
    QUIZ = "quiz"


@dataclass(frozen=True)
class ModelChoice:
    model: str
    reason: str


class ModelRouter:
    def __init__(
        self,
        default_model: str = "gpt-4o-mini",
        strong_model: str = "gpt-4o",
        struggle_threshold: int = 3,
    ) -> None:
        self._default = default_model
        self._strong = strong_model
        self._struggle_threshold = struggle_threshold

    def select(
        self,
        task: LlmTask,
        decision: PedagogicalDecision | None = None,
        *,
        struggle_signals: int = 0,
        json_retry: bool = False,
    ) -> ModelChoice:
        if json_retry:
            return ModelChoice(self._strong, "json_retry")

        if task == LlmTask.ANALYZE:
            return ModelChoice(self._default, "analyze_structured")

        if task == LlmTask.QUIZ:
            if decision and decision.blocked_by_prereq:
                return ModelChoice(self._default, "quiz_remediation")
            return ModelChoice(self._default, "quiz_json")

        # ASK
        if decision is None:
            return ModelChoice(self._default, "ask_default")
        if (
            decision.mode == PedagogicalMode.SOCRATIC
            and decision.target_difficulty.value == "hard"
        ):
            return ModelChoice(self._strong, "socratic_hard")
        if struggle_signals >= self._struggle_threshold:
            return ModelChoice(self._strong, "high_struggle")
        if decision.blocked_by_prereq:
            return ModelChoice(self._default, "prereq_scaffold")
        return ModelChoice(self._default, "ask_default")
