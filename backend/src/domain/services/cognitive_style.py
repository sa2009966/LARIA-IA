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


#: Pedidos EXPLÍCITOS de forma ("explícamelo paso a paso", "hazme un dibujo").
#: Más estrictos que `_STYLE_HINTS` a propósito: "ecuación" es un tema, no un
#: pedido de fórmulas, y no puede pisar el estilo que el estudiante eligió.
_STYLE_REQUESTS: list[tuple[str, CognitiveStyle]] = [
    (r"paso\s+a\s+paso|paso\s+por\s+paso|desgl[oó]sa", CognitiveStyle.STEP_BY_STEP),
    (r"analog[ií]a|met[aá]fora", CognitiveStyle.ANALOGY),
    (
        r"(?:con|haz|hazme|usa|pon|ponme)\s+(?:un|una)?\s*(?:dibujo|diagrama|esquema|gr[aá]fico)"
        r"|dib[uú]ja(?:lo|me)",
        CognitiveStyle.VISUAL,
    ),
    (r"con\s+(?:las\s+)?f[oó]rmulas|demu[eé]stra(?:lo|me)", CognitiveStyle.MATHEMATICAL),
    (r"m[aá]s\s+t[eé]cnic|riguros|formalmente", CognitiveStyle.TECHNICAL),
    (
        r"m[aá]s\s+(?:simple|f[aá]cil|sencill)|en\s+palabras\s+(?:simples|sencillas)"
        r"|expl[ií]ca(?:lo|me)(?:lo)?\s+(?:f[aá]cil|sencillo|simple)",
        CognitiveStyle.SIMPLE,
    ),
]


def style_requested_in(text: str) -> CognitiveStyle | None:
    """El estilo que el mensaje pide de forma explícita, o None."""
    import re

    for pattern, style in _STYLE_REQUESTS:
        if re.search(pattern, text or "", re.IGNORECASE):
            return style
    return None


def chosen_style(profile: StudentProfile | None) -> CognitiveStyle | None:
    """El estilo que el estudiante eligió él mismo (ADR-022), o None."""
    if profile is None or not profile.explanation_style_choice:
        return None
    try:
        return CognitiveStyle(profile.explanation_style_choice)
    except ValueError:
        return None


class CognitiveStyleSelector:
    """Elige estilo de explicación a partir de preferencia, señales y ritmo."""

    def select(
        self,
        profile: StudentProfile | None,
        question: str = "",
        signal: LearningSignal | None = None,
    ) -> CognitiveStyle:
        import re

        # Lo que pide en este mensaje gana; después, lo que eligió (ADR-022).
        # Lo deducido —palabras sueltas, señales, memoria— solo decide si no
        # dijo nada: adivinar no puede pisar una preferencia declarada.
        pedido = style_requested_in(question)
        if pedido is not None:
            return pedido
        elegido = chosen_style(profile)
        if elegido is not None:
            return elegido

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
