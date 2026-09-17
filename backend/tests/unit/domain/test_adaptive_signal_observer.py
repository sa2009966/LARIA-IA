"""El observador traduce hechos del turno en observaciones (ADR-004, Decisión 2)."""
import pytest

from src.domain.adaptive_signals import DEFAULT_CUTOFFS, SignalKind
from src.domain.services.adaptive_signal_observer import (
    AdaptiveSignalObserver,
    TurnFacts,
)

SESSION_GAP_MS = DEFAULT_CUTOFFS.session_gap_minutes * 60_000
LARGA = DEFAULT_CUTOFFS.long_explanation_chars


def observe(question="pregunta", gap_ms=None, previous_answer_length=0):
    return AdaptiveSignalObserver().observe(
        TurnFacts(
            question=question,
            gap_ms=gap_ms,
            previous_answer_length=previous_answer_length,
        )
    )


def test_sin_gap_no_observa_senales_temporales():
    """Primer turno: no hay nada que medir en el tiempo."""
    out = observe(gap_ms=None)
    assert SignalKind.RESPONSE_LATENCY not in out
    assert SignalKind.ATTENTION_SPAN not in out
    assert SignalKind.LONG_EXPLANATION_ABANDONMENT not in out


def test_abandono_requiere_explicacion_larga_previa():
    """Sin explicación larga previa no hay nada que abandonar."""
    out = observe(gap_ms=SESSION_GAP_MS * 2, previous_answer_length=10)
    assert SignalKind.LONG_EXPLANATION_ABANDONMENT not in out


def test_explicacion_larga_mas_silencio_es_abandono():
    out = observe(gap_ms=SESSION_GAP_MS * 2, previous_answer_length=LARGA)
    assert out[SignalKind.LONG_EXPLANATION_ABANDONMENT] == 1.0
    assert out[SignalKind.ATTENTION_SPAN] == 0.0


def test_explicacion_larga_continuada_no_es_abandono():
    out = observe(gap_ms=1_000, previous_answer_length=LARGA)
    assert out[SignalKind.LONG_EXPLANATION_ABANDONMENT] == 0.0
    assert out[SignalKind.ATTENTION_SPAN] == 1.0


def test_latencia_se_normaliza_y_satura():
    assert observe(gap_ms=SESSION_GAP_MS / 2)[SignalKind.RESPONSE_LATENCY] == pytest.approx(0.5)
    assert observe(gap_ms=SESSION_GAP_MS * 10)[SignalKind.RESPONSE_LATENCY] == 1.0


@pytest.mark.parametrize(
    "texto,esperada",
    [
        ("no entiendo nada", SignalKind.CLARIFICATION_RATE),
        ("dame un ejemplo", SignalKind.EXAMPLE_REQUEST_RATE),
        ("ponme ejercicios", SignalKind.PRACTICE_SEEKING),
        ("ah claro, ya entendí", SignalKind.SELF_CORRECTION),
        ("explícamelo como si fuera un juego", SignalKind.ANALOGY_AFFINITY),
    ],
)
def test_senales_de_texto(texto, esperada):
    assert observe(question=texto)[esperada] == 1.0


def test_texto_neutro_observa_cero_no_ausencia():
    """Observar 0 alimenta el gate de muestras; no observar, no."""
    out = observe(question="¿cuál es la capital de Francia?")
    assert out[SignalKind.CLARIFICATION_RATE] == 0.0


def test_confidence_expression_vive_fuera_del_flujo_de_politica():
    observador = AdaptiveSignalObserver()
    out = observador.observe(TurnFacts("no entiendo", None, 0))
    assert SignalKind.CONFIDENCE_EXPRESSION not in out
    assert observador.observe_confidence_expression(0.8) == pytest.approx(0.2)
