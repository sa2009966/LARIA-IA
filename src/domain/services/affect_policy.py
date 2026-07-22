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
        if decision and decision.mode == PedagogicalMode.SCAFFOLD:
            return AffectState.PATIENT
        if profile and profile.pace == "slow":
            return AffectState.ENCOURAGING
        if decision and decision.mode == PedagogicalMode.SOCRATIC:
            return AffectState.CALM
        return AffectState.ENCOURAGING
