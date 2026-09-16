"""Tests de la política adaptativa (ADR-004).

Blindan las cuatro decisiones: precedencia, gate de muestras, ortogonalidad de
señales derivadas y pertenencia de todo parámetro a una familia.
"""
import inspect

import pytest

from src.domain.services.adaptive_policy import (
    DERIVED_FROM,
    OBSERVATIONAL_SIGNALS,
    POLICY_SIGNALS,
    AdaptationCutoffs,
    AdaptationParameters,
    AdaptivePolicy,
    ControlFlowParameters,
    PromptShapingParameters,
    Signal,
    SignalKind,
)

CUT = AdaptationCutoffs()


def signal(kind: SignalKind, value: float, samples: int | None = None) -> Signal:
    """Señal ya madura (por encima del gate) salvo que se pida lo contrario."""
    return Signal(
        kind=kind,
        value=value,
        samples=CUT.min_samples_for_adaptation if samples is None else samples,
    )


def profile(*signals: Signal) -> dict[SignalKind, Signal]:
    return {s.kind: s for s in signals}


# --- Punto 1: conflicto de señales --------------------------------------------------


def test_abandono_alto_gana_a_attention_span_alto():
    """Invariante del ADR-004: conducta observada > proxy inferido.

    Es el test que blinda el bug: si la política resolviera por orden de `if`,
    `attention_span` sobrescribiría al abandono y el estudiante recibiría
    explicaciones largas justo cuando las abandona.
    """
    params = AdaptivePolicy().decide(
        profile(
            signal(SignalKind.LONG_EXPLANATION_ABANDONMENT, 0.9),
            signal(SignalKind.ATTENTION_SPAN, 0.95),
        )
    )
    assert params.prompt_shaping.explanation_length == "short"
    assert params.prompt_shaping.explanation_length != "long"


def test_attention_span_alto_sin_abandono_da_long():
    params = AdaptivePolicy().decide(
        profile(
            signal(SignalKind.ATTENTION_SPAN, 0.95),
            signal(SignalKind.LONG_EXPLANATION_ABANDONMENT, 0.1),
        )
    )
    assert params.prompt_shaping.explanation_length == "long"


def test_sin_senales_concluyentes_cae_a_medium():
    params = AdaptivePolicy().decide(profile())
    assert params.prompt_shaping.explanation_length == "medium"


@pytest.mark.parametrize("abandono", [0.56, 0.7, 1.0])
def test_abandono_sobre_el_cutoff_siempre_acorta(abandono):
    params = AdaptivePolicy().decide(
        profile(
            signal(SignalKind.LONG_EXPLANATION_ABANDONMENT, abandono),
            signal(SignalKind.ATTENTION_SPAN, 1.0),
        )
    )
    assert params.prompt_shaping.explanation_length == "short"


def test_gate_de_muestras_ignora_senales_inmaduras():
    """Una señal por debajo de MIN_SAMPLES no adapta nada."""
    params = AdaptivePolicy().decide(
        profile(signal(SignalKind.LONG_EXPLANATION_ABANDONMENT, 0.99, samples=1))
    )
    assert params.prompt_shaping.explanation_length == "medium"


def test_cutoffs_son_configurables():
    laxa = AdaptivePolicy(AdaptationCutoffs(abandonment=0.95))
    params = laxa.decide(
        profile(
            signal(SignalKind.LONG_EXPLANATION_ABANDONMENT, 0.6),
            signal(SignalKind.ATTENTION_SPAN, 0.9),
        )
    )
    assert params.prompt_shaping.explanation_length == "long"


# --- Parámetros sin conflicto -------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected", [(0.9, 3), (0.5, 2), (0.1, 1)]
)
def test_examples_por_banda(value, expected):
    params = AdaptivePolicy().decide(profile(signal(SignalKind.EXAMPLE_REQUEST_RATE, value)))
    assert params.prompt_shaping.examples_per_explanation == expected


@pytest.mark.parametrize(
    "value,expected", [(0.9, "high"), (0.5, "medium"), (0.1, "low")]
)
def test_socratic_rate_por_banda(value, expected):
    params = AdaptivePolicy().decide(profile(signal(SignalKind.SELF_CORRECTION, value)))
    assert params.prompt_shaping.socratic_question_rate == expected


def test_control_flow_se_deriva_de_sus_senales():
    params = AdaptivePolicy().decide(
        profile(
            signal(SignalKind.PRACTICE_SEEKING, 0.8),
            signal(SignalKind.RESPONSE_LATENCY, 0.9),
        )
    )
    assert params.control_flow.practice_before_advance is True
    assert params.control_flow.chunk_explanation is True


# --- Punto 4: entanglement ----------------------------------------------------------


def test_confidence_expression_no_es_senal_de_politica():
    assert SignalKind.CONFIDENCE_EXPRESSION in OBSERVATIONAL_SIGNALS
    assert SignalKind.CONFIDENCE_EXPRESSION not in POLICY_SIGNALS


def test_confidence_expression_no_altera_ninguna_decision():
    """Aunque un llamador la pase, no puede llegar a ninguna rama."""
    base = AdaptivePolicy().decide(profile(signal(SignalKind.CLARIFICATION_RATE, 0.8)))
    contaminado = AdaptivePolicy().decide(
        profile(
            signal(SignalKind.CLARIFICATION_RATE, 0.8),
            signal(SignalKind.CONFIDENCE_EXPRESSION, 0.99),
        )
    )
    assert base == contaminado


def test_ninguna_derivada_convive_con_su_componente_en_la_politica():
    """Regla escrita del ADR-004, verificada sobre la declaración misma."""
    for derived, component in DERIVED_FROM.items():
        assert derived not in POLICY_SIGNALS
        assert component in POLICY_SIGNALS


def test_confidence_expression_no_aparece_en_el_codigo_de_la_politica():
    source = inspect.getsource(AdaptivePolicy)
    assert "CONFIDENCE_EXPRESSION" not in source
    assert "confidence_expression" not in source


# --- Punto 3: familias --------------------------------------------------------------


def test_todo_parametro_pertenece_a_una_familia():
    campos = set(AdaptationParameters.__dataclass_fields__)
    assert campos == {"prompt_shaping", "control_flow"}


def test_prompt_shaping_produce_fragmento_de_prompt():
    fragmento = PromptShapingParameters(
        explanation_length="short", examples_per_explanation=2, prefers_analogy=True
    ).to_prompt_fragment()
    assert "breve" in fragmento
    assert "2 ejemplo" in fragmento
    assert "analogía" in fragmento


def test_control_flow_no_produce_prompt():
    assert not hasattr(ControlFlowParameters(), "to_prompt_fragment")


# --- EWMA ---------------------------------------------------------------------------


def test_primera_observacion_fija_el_valor():
    s = Signal(kind=SignalKind.CLARIFICATION_RATE).observe(0.8, alpha=0.3)
    assert s.value == pytest.approx(0.8)
    assert s.samples == 1


def test_ewma_suaviza_observaciones_posteriores():
    s = Signal(kind=SignalKind.CLARIFICATION_RATE).observe(1.0, alpha=0.3).observe(0.0, alpha=0.3)
    assert s.value == pytest.approx(0.7)
    assert s.samples == 2


def test_observaciones_se_recortan_a_0_1():
    s = Signal(kind=SignalKind.CLARIFICATION_RATE).observe(5.0, alpha=0.3)
    assert s.value == 1.0
