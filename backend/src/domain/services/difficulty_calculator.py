"""Cálculo de dificultad a partir de evidencia (zona de desafío)."""
from __future__ import annotations

from dataclasses import dataclass

from src.domain.aggregates.student_profile import StudentProfile
from src.domain.value_objects.question import Difficulty


@dataclass(frozen=True)
class DifficultySignals:
    effective_mastery: float
    confidence: float
    learning_velocity: float
    recent_error_rate: float
    pace: str = "steady"


class DifficultyCalculator:
    """Mantiene al estudiante en zona de desafío adecuada."""

    def from_profile(
        self,
        profile: StudentProfile | None,
        focus_concepts: tuple[str, ...] = (),
    ) -> Difficulty:
        if profile is None:
            return Difficulty.MEDIUM

        if focus_concepts:
            masteries = [profile.effective_concept_mastery(c) for c in focus_concepts]
            confidences = []
            errors = 0
            for c in focus_concepts:
                entry = profile.mastery_by_concept.get(c)
                if entry is None:
                    confidences.append(0.0)
                    continue
                confidences.append(entry.confidence)
                if entry.error_streak > 0 or entry.last_score_ratio < 0.5:
                    errors += 1
            eff = min(masteries) if masteries else 0.0
            conf = sum(confidences) / len(confidences) if confidences else 0.0
            err_rate = errors / max(1, len(focus_concepts))
        else:
            docs = list(profile.mastery_by_document.values())
            eff = min((d.mastery for d in docs), default=0.0)
            conf = 0.3
            err_rate = 0.0

        return self.calculate(
            DifficultySignals(
                effective_mastery=eff,
                confidence=conf,
                learning_velocity=profile.learning_velocity,
                recent_error_rate=err_rate,
                pace=profile.pace,
            )
        )

    def calculate(self, signals: DifficultySignals) -> Difficulty:
        score = signals.effective_mastery
        # Baja confianza o muchos errores → más fácil
        score -= 0.15 * (1.0 - max(0.0, min(1.0, signals.confidence)))
        score -= 0.2 * max(0.0, min(1.0, signals.recent_error_rate))
        # Velocidad positiva permite subir un poco
        score += 0.1 * max(-0.5, min(0.5, signals.learning_velocity)) * 2
        if signals.pace == "slow":
            score -= 0.1
        elif signals.pace == "fast":
            score += 0.08

        if score < 0.38:
            return Difficulty.EASY
        if score < 0.72:
            return Difficulty.MEDIUM
        return Difficulty.HARD
