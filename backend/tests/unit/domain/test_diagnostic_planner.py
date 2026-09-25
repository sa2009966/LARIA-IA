"""Nivelación por rondas: qué se pregunta y qué veredicto sale (ADR-017).

Reescritos desde el ADR-016, que administraba **una** tanda mezclada de seis
ítems. Lo que aquellos tests protegían —que hay escalera de dificultad y que lo
fácil prueba la base— sigue aquí, ahora dentro de cada ronda. Lo que se añade es
el veredicto, que es lo que el ADR-016 no daba.
"""
import pytest

from src.domain.catalog.prerequisite_seeds import build_seeded_graph
from src.domain.services.diagnostic_planner import (
    MAX_PREREQUISITES,
    PASSING_RATIO,
    PlacementLevel,
    PlacementRound,
    has_next_round,
    plan_diagnostic,
    resolve_placement,
    round_for,
)
from src.domain.value_objects.question import Difficulty


def grafo():
    return build_seeded_graph()


# --- Qué se pregunta en cada ronda ---------------------------------------------------


def test_la_ronda_base_pesa_lo_facil_y_la_avanzada_lo_dificil():
    base = plan_diagnostic("ecuaciones", grafo(), PlacementRound.BASE)
    avanzada = plan_diagnostic("ecuaciones", grafo(), PlacementRound.AVANZADA)

    assert base.total_items == 6
    assert avanzada.total_items == 8
    assert [r.difficulty for r in base.rungs] == [Difficulty.EASY, Difficulty.MEDIUM]
    assert [r.difficulty for r in avanzada.rungs] == [Difficulty.MEDIUM, Difficulty.HARD]
    # La avanzada no baja a lo fácil: ya se demostró.
    assert Difficulty.EASY not in [r.difficulty for r in avanzada.rungs]


def test_lo_facil_prueba_la_base_y_el_resto_el_tema():
    """Es lo que hace que suspender la ronda base señale un hueco de prerrequisito."""
    plan = plan_diagnostic("ecuaciones lineales", grafo(), PlacementRound.BASE)
    facil, media = plan.rungs

    assert set(facil.concepts) == set(plan.prerequisites)
    assert media.concepts == (plan.topic,)


def test_se_limitan_los_prerrequisitos():
    plan = plan_diagnostic("resolver ecuación", grafo())

    assert len(plan.prerequisites) <= MAX_PREREQUISITES


def test_el_tema_se_canoniza_por_alias():
    assert plan_diagnostic("ecuaciones", grafo()).topic == "ecuaciones lineales"


def test_el_plan_dice_a_que_ronda_pertenece():
    """El projector lo necesita para saber qué veredicto escribir."""
    assert plan_diagnostic("derivadas", grafo(), PlacementRound.AVANZADA).round is (
        PlacementRound.AVANZADA
    )


# --- Qué ronda toca ------------------------------------------------------------------


@pytest.mark.parametrize(
    "nivel, esperada",
    [
        (None, PlacementRound.BASE),
        (PlacementLevel.BASICO, PlacementRound.BASE),
        (PlacementLevel.INTERMEDIO, PlacementRound.AVANZADA),
        (PlacementLevel.AVANZADO, PlacementRound.AVANZADA),
    ],
)
def test_la_ronda_sale_del_nivel_guardado(nivel, esperada):
    """El cliente no lleva estado: pide "evalúame" y el backend sabe por dónde va."""
    assert round_for(nivel) is esperada


# --- El veredicto --------------------------------------------------------------------


@pytest.mark.parametrize(
    "ronda, acierto, esperado",
    [
        (PlacementRound.BASE, 0.5, PlacementLevel.BASICO),
        (PlacementRound.BASE, PASSING_RATIO, PlacementLevel.INTERMEDIO),
        (PlacementRound.AVANZADA, 0.5, PlacementLevel.INTERMEDIO),
        (PlacementRound.AVANZADA, 1.0, PlacementLevel.AVANZADO),
    ],
)
def test_cada_ronda_da_su_veredicto(ronda, acierto, esperado):
    assert resolve_placement(ronda, acierto) is esperado


def test_aprobar_es_exigente():
    """Un falso 'avanzado' hace más daño que un falso 'intermedio'."""
    justo_debajo = PASSING_RATIO - 0.01

    assert resolve_placement(PlacementRound.AVANZADA, justo_debajo) is PlacementLevel.INTERMEDIO
    assert PASSING_RATIO >= 0.7


def test_un_mal_dia_no_borra_lo_demostrado():
    """Suspender la avanzada no degrada a quien ya era avanzado."""
    nivel = resolve_placement(PlacementRound.AVANZADA, 0.1, PlacementLevel.AVANZADO)

    assert nivel is PlacementLevel.AVANZADO


# --- Cuándo hay otra ronda -----------------------------------------------------------


def test_solo_se_avanza_de_ronda_aprobando():
    assert has_next_round(PlacementRound.BASE, PlacementLevel.INTERMEDIO) is True
    assert has_next_round(PlacementRound.BASE, PlacementLevel.BASICO) is False


def test_suspender_la_avanzada_no_la_vuelve_a_ofrecer():
    """El bucle que casi se cuela: quien suspende la avanzada también queda
    en `intermedio`, y mirando solo el nivel se le ofrecería repetirla sin fin."""
    assert has_next_round(PlacementRound.AVANZADA, PlacementLevel.INTERMEDIO) is False
    assert has_next_round(PlacementRound.AVANZADA, PlacementLevel.AVANZADO) is False


# --- Degradación --------------------------------------------------------------------


def test_un_tema_fuera_del_curriculo_sigue_siendo_nivelable():
    plan = plan_diagnostic("cocina tailandesa", grafo())

    assert plan.topic == "cocina tailandesa"
    assert plan.prerequisites == ()
    assert all(r.concepts == ("cocina tailandesa",) for r in plan.rungs)


def test_un_tema_vacio_es_un_error_util():
    with pytest.raises(ValueError, match="tema"):
        plan_diagnostic("   ")


def test_el_mismo_tema_y_ronda_producen_el_mismo_plan():
    assert plan_diagnostic("derivadas", grafo()) == plan_diagnostic("derivadas", grafo())
