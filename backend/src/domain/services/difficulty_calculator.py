"""Cálculo de dificultad a partir de evidencia (zona de desafío)."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.domain.aggregates.student_profile import StudentProfile
from src.domain.value_objects.question import Difficulty

#: Peso de la velocidad de aprendizaje en el score. Estaba escrito como
#: `0.1 * clamp(v) * 2`, que es 0.2 y no el 0.1 que documentaba la auditoría.
_VELOCITY_WEIGHT = 0.2


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
        document_id: UUID | None = None,
    ) -> Difficulty:
        if profile is None:
            return Difficulty.MEDIUM

        if focus_concepts:
            # Solo los conceptos con evidencia deciden la dificultad. Un
            # concepto sin medir no aporta un 0.0 que empuje a EASY: eso
            # dejaría al estudiante por debajo de su nivel real (ADR-006).
            # Un único auto-reporte tampoco basta: existir en el perfil no es
            # lo mismo que haber sido medido (ADR-007).
            measured = [c for c in focus_concepts if profile.has_decision_evidence(c)]
            if not measured:
                return Difficulty.MEDIUM
            masteries = [profile.effective_concept_mastery(c) for c in measured]
            confidences = []
            errors = 0
            for c in measured:
                entry = profile.mastery_by_concept[c]
                confidences.append(entry.confidence)
                if entry.error_streak > 0 or entry.last_score_ratio < 0.5:
                    errors += 1
            eff = min(masteries)
            conf = sum(confidences) / len(confidences)
            err_rate = errors / len(measured)
        else:
            # Sin foco conceptual, el material del turno es la única evidencia
            # pertinente. Antes se tomaba `min()` sobre TODOS los documentos:
            # el documento peor dominado fijaba la dificultad de un tema que no
            # tenía nada que ver, y sin documentos daba 0.0 ⇒ EASY, castigando
            # de nuevo la falta de datos (ADR-006).
            entry = (
                profile.mastery_by_document.get(document_id)
                if document_id is not None
                else None
            )
            if entry is None or entry.attempts == 0:
                return Difficulty.MEDIUM
            eff = entry.mastery
            conf = 0.3
            err_rate = 1.0 if entry.incorrect_streak > 0 else 0.0

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
        score += _VELOCITY_WEIGHT * max(-0.5, min(0.5, signals.learning_velocity))
        if signals.pace == "slow":
            score -= 0.1
        elif signals.pace == "fast":
            score += 0.08

        if score < 0.38:
            return Difficulty.EASY
        if score < 0.72:
            return Difficulty.MEDIUM
        return Difficulty.HARD
