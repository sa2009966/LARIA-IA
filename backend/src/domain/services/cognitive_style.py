"""Inferencia de estilo cognitivo de explicación."""
from __future__ import annotations

from enum import Enum

from src.domain.aggregates.student_profile import StudentProfile
from src.domain.services.learning_signal_detector import LearningSignal, LearningSignalKind


class CognitiveStyle(str, Enum):
    SIMPLE = "simple"
    TECHNICAL = "technical"
    MATHEMATICAL = "mathematical"
    ANALOGY = "analogy"
    VISUAL = "visual"
    STEP_BY_STEP = "step_by_step"


_STYLE_HINTS: list[tuple[str, CognitiveStyle]] = [
    (r"paso a paso|paso\s+por\s+paso|desglosa", CognitiveStyle.STEP_BY_STEP),
    (r"analog[ií]a|como si|como\s+cuando|metaf[oó]ra", CognitiveStyle.ANALOGY),
    (r"visual|diagrama|dibuja|esquema", CognitiveStyle.VISUAL),
    (r"f[oó]rmula|matem[aá]tic|ecuaci[oó]n|demuestra", CognitiveStyle.MATHEMATICAL),
    (r"t[eé]cnic|formal|riguroso", CognitiveStyle.TECHNICAL),
    (r"simple|f[aá]cil|sencill|principiante", CognitiveStyle.SIMPLE),
]


class CognitiveStyleSelector:
    """Elige estilo de explicación a partir de preferencia, señales y ritmo."""

    def select(
        self,
        profile: StudentProfile | None,
        question: str = "",
        signal: LearningSignal | None = None,
    ) -> CognitiveStyle:
        import re

        text = (question or "").lower()
        for pattern, style in _STYLE_HINTS:
            if re.search(pattern, text, re.IGNORECASE):
                return style

        if signal is not None:
            if signal.kind in (LearningSignalKind.NOVICE, LearningSignalKind.CONFUSION):
                return CognitiveStyle.SIMPLE
            if signal.kind == LearningSignalKind.HELP:
                return CognitiveStyle.STEP_BY_STEP

        if profile is not None:
            preferred = (profile.pedagogical_memory.preferred_explanation_style or "").lower()
            for style in CognitiveStyle:
                if preferred == style.value:
                    return style
            if profile.pace == "slow" or profile.total_struggle_signals >= 3:
                return CognitiveStyle.STEP_BY_STEP
            if profile.pace == "fast" and profile.total_attempts >= 4:
                return CognitiveStyle.TECHNICAL

        return CognitiveStyle.SIMPLE
