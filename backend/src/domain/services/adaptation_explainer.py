"""Decir por qué el tutor está hablando así.

*"Te doy más ejemplos porque los has pedido varias veces."* Una adaptación que
no se explica es indistinguible de la arbitrariedad —o de un juicio sobre el
estudiante—; explicarla la convierte en colaboración y desarrolla metacognición
(P5 del plan de experiencia pedagógica).

Y antes de eso es un **instrumento de depuración**: cuando se apague el modo
sombra y una respuesta salga rara, esta frase dice si falló la señal, la
política o el arbitraje. Sin ella se adivina contra un LLM.

Dos reglas que lo mantienen honesto:

1. **Solo se explica lo que se aplicó.** La frase se construye desde los
   parámetros **efectivos** (ya arbitrados por `plan_composer`), no desde lo que
   la política pidió. Si el andamiaje vetó la brevedad, se cuenta eso.
2. **Se nombra la conducta, no el número.** "Sueles abandonar las explicaciones
   largas", no "tu `long_explanation_abandonment` es 0.91". El estudiante no
   tiene por qué conocer nuestras métricas, y el número sin contexto asusta.
"""
from __future__ import annotations

from collections.abc import Mapping

from src.domain.adaptive_signals import Signal, SignalKind
from src.domain.services.adaptive_policy import (
    ControlFlowParameters,
    PromptShapingParameters,
)
from src.domain.services.plan_composer import Override

#: Cuántos motivos caben en una frase antes de volverse ruido. Dos: el tutor
#: explica, no rinde cuentas.
MAX_MOTIVOS = 2

#: Parámetro efectivo → (señal que lo gobierna, cómo se le cuenta al estudiante).
#: La señal se nombra para poder comprobar que de verdad está presente: sin
#: señal no hay causa, y sin causa no se afirma nada.
_MOTIVOS_PROMPT: list[tuple[str, object, SignalKind, str]] = [
    (
        "explanation_length",
        "short",
        SignalKind.LONG_EXPLANATION_ABANDONMENT,
        "voy al grano porque las explicaciones largas se te hacen cuesta arriba",
    ),
    (
        "explanation_length",
        "long",
        SignalKind.ATTENTION_SPAN,
        "me extiendo más porque sueles quedarte hasta el final",
    ),
    (
        "socratic_question_rate",
        "high",
        SignalKind.SELF_CORRECTION,
        "te pregunto más de lo que te cuento porque sueles llegar tú a la respuesta",
    ),
    (
        "socratic_question_rate",
        "medium",
        SignalKind.SELF_CORRECTION,
        "intercalo preguntas porque razonando en voz alta te sale",
    ),
    (
        "prefers_analogy",
        True,
        SignalKind.ANALOGY_AFFINITY,
        "empiezo con una analogía porque contigo funcionan",
    ),
]

_MOTIVOS_FLUJO: list[tuple[str, SignalKind, str]] = [
    (
        "practice_before_advance",
        SignalKind.PRACTICE_SEEKING,
        "te propongo practicar antes de avanzar porque es lo que sueles pedir",
    ),
    (
        "chunk_explanation",
        SignalKind.RESPONSE_LATENCY,
        "voy por partes para que puedas seguir el ritmo",
    ),
]

#: Motivo del veto → cómo se le cuenta al estudiante. El arbitraje es la mitad
#: más interesante de la explicación: dice qué NO se hizo y por qué.
_MOTIVOS_VETO: dict[str, str] = {
    "explanation_length": "no acorto la explicación porque estamos construyendo la base",
    "socratic_question_rate": "ahora te acompaño en vez de preguntarte, para no dejarte solo en un punto que cuesta",
    "examples_per_explanation": "incluyo un ejemplo porque es la forma del andamiaje",
    "prefers_analogy": "no repito la analogía porque ya está en el estilo de la explicación",
    "chunk_explanation": "no troceo una respuesta que ya es breve",
}


def _hay_senal(signals: Mapping[SignalKind, Signal], kind: SignalKind) -> bool:
    """Si la señal existe con alguna observación detrás."""
    signal = signals.get(kind)
    return signal is not None and signal.samples > 0


def explain_adaptation(
    shaping: PromptShapingParameters,
    control_flow: ControlFlowParameters,
    signals: Mapping[SignalKind, Signal],
    overrides: tuple[Override, ...] = (),
    *,
    examples_por_defecto: int = 1,
) -> str:
    """Frase en lenguaje natural, o cadena vacía si no hubo nada que adaptar.

    Vacío es una respuesta legítima: a un estudiante sin historial no se le
    inventa un porqué.
    """
    motivos: list[str] = []

    for parametro, valor, senal, frase in _MOTIVOS_PROMPT:
        if getattr(shaping, parametro) == valor and _hay_senal(signals, senal):
            motivos.append(frase)

    if shaping.examples_per_explanation > examples_por_defecto and _hay_senal(
        signals, SignalKind.EXAMPLE_REQUEST_RATE
    ):
        cantidad = shaping.examples_per_explanation
        motivos.append(
            f"te pongo {cantidad} ejemplos porque los has pedido varias veces"
        )

    for parametro, senal, frase in _MOTIVOS_FLUJO:
        if getattr(control_flow, parametro) and _hay_senal(signals, senal):
            motivos.append(frase)

    # Los vetos van al final: matizan lo anterior ("me extiendo… pero no acorto
    # porque…" sería contradictorio al revés).
    for veto in overrides:
        frase = _MOTIVOS_VETO.get(veto.parameter)
        if frase and frase not in motivos:
            motivos.append(frase)

    if not motivos:
        return ""
    return _unir(motivos[:MAX_MOTIVOS])


def _unir(motivos: list[str]) -> str:
    """Una frase, con mayúscula y punto. Dos motivos se unen con 'y'."""
    cuerpo = motivos[0] if len(motivos) == 1 else f"{motivos[0]}, y {motivos[1]}"
    return cuerpo[0].upper() + cuerpo[1:] + "."
