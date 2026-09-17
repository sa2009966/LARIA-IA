"""Política afectiva discreta derivada del perfil/decisión (no del LLM)."""
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.ports.embodiment import AffectState
from src.domain.services.pedagogical_engine import PedagogicalDecision, PedagogicalMode


class AffectPolicy:
    def select(
        self,
        profile: StudentProfile | None,
        decision: PedagogicalDecision | None = None,
        last_score_ratio: float | None = None,
    ) -> AffectState:
        if last_score_ratio is not None and last_score_ratio >= 0.85:
            return AffectState.CELEBRATORY
        # Andamiaje o ritmo lento piden paciencia. El ritmo lento devolvía
        # ENCOURAGING, que es el default: la rama existía sin cambiar nada
        # (ADR-008).
        if (decision and decision.mode == PedagogicalMode.SCAFFOLD) or (
            profile and profile.pace == "slow"
        ):
            return AffectState.PATIENT
        if decision and decision.mode == PedagogicalMode.SOCRATIC:
            return AffectState.CALM
        return AffectState.ENCOURAGING
