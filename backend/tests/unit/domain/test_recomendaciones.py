"""Lo que el motor de recomendaciones promete al estudiante (fase F).

Se escribieron después de ejercitarlo por primera vez con perfiles realistas.
Hasta entonces solo tenía 8 referencias en un archivo de tests y nadie había
mirado la lista que produce de verdad: eran diez filas sobre tres conceptos.
"""
from uuid import uuid4

import pytest

from src.domain.aggregates.student_profile import StudentProfile
from src.domain.catalog.prerequisite_seeds import build_seeded_graph
from src.domain.services.prerequisite_graph import PrerequisiteGate
from src.domain.services.recommendation_engine import RecommendationEngine


def motor() -> RecommendationEngine:
    return RecommendationEngine(PrerequisiteGate(build_seeded_graph()))


def perfil_que_falla(*conceptos: str, veces: int = 2) -> StudentProfile:
    profile = StudentProfile.create(uuid4())
    for concepto in conceptos:
        for _ in range(veces):
            profile.record_concept_result(concepto, 0.1)
    return profile


# --- Un concepto, una recomendación ---------------------------------------------------


def test_un_concepto_no_aparece_dos_veces():
    """El defecto que hacía inservible la lista.

    La deduplicación era por `(kind, concepto, documento)`, así que el mismo
    concepto salía como "olvidado", "prioridad de repaso" y "repasa": tres
    filas con el mismo contenido, llenando el tope de diez.
    """
    profile = perfil_que_falla("funciones", "ecuacion", "variable")

    recs = motor().build(profile)

    conceptos = [r.concept for r in recs if r.concept]
    assert len(conceptos) == len(set(conceptos))


def test_el_tiempo_sugerido_no_cuenta_el_mismo_concepto_varias_veces():
    """Se calculaba antes de deduplicar, así que sumaba duplicados."""
    profile = perfil_que_falla("funciones")

    recs = motor().build(profile)

    tiempo = next(r for r in recs if r.kind == "study_time")
    otras = [r for r in recs if r.kind != "study_time"][:3]
    assert tiempo.suggested_minutes == sum(r.suggested_minutes or 10 for r in otras)


# --- Lo que bloquea se dice ------------------------------------------------------------


def test_se_nombra_lo_que_el_concepto_debil_esta_frenando():
    """Antes esto valía `×1.2` de prioridad y ningún mensaje.

    Un estudiante al que se le pide repasar algo que no preguntó merece saber
    por qué. Es la misma regla que el ADR-006 aplicó al gate: nunca desviar en
    silencio.
    """
    profile = perfil_que_falla("jerarquía de operaciones")

    recs = motor().build(profile)

    desbloqueo = next(r for r in recs if r.kind == "unblock")
    assert desbloqueo.concept == "jerarquia de operaciones"
    assert "resolver ecuacion" in desbloqueo.message


def test_lo_que_bloquea_se_busca_hacia_adelante_en_el_grafo():
    """El caso que se perdía entero, y es el más común.

    Se recorría `mastery_by_concept`, así que un hueco solo contaba como
    bloqueante si el concepto bloqueado **ya tenía evidencia**. Quien falla el
    orden de las operaciones todavía no ha intentado despejar una ecuación:
    justamente por eso está bloqueado.
    """
    profile = perfil_que_falla("jerarquía de operaciones")
    assert "resolver ecuacion" not in profile.mastery_by_concept  # nunca lo tocó

    recs = motor().build(profile)

    assert any(r.kind == "unblock" for r in recs)


def test_un_concepto_debil_que_no_frena_nada_no_dice_que_frena():
    """`leyes de newton` es una hoja del currículum: no habilita a nada."""
    profile = perfil_que_falla("leyes de newton")

    recs = motor().build(profile)

    assert any(r.kind == "review_priority" for r in recs)
    assert not any(r.kind == "unblock" for r in recs)


# --- Variedad: el criterio de cierre de la fase ---------------------------------------


def test_un_perfil_con_historial_produce_recomendaciones_variadas():
    """Criterio de cierre: tres recomendaciones priorizadas, variadas y
    defendibles en voz alta."""
    profile = StudentProfile.create(uuid4())
    for _ in range(7):
        profile.record_concept_result("variable", 1.0)
    for _ in range(2):
        profile.record_concept_result("ecuación cuadrática", 0.1)

    recs = motor().build(profile)

    assert len(recs) >= 3
    assert len({r.kind for r in recs}) >= 3
    assert recs == sorted(recs, key=lambda r: r.priority, reverse=True)


def test_el_perfil_vacio_recibe_por_donde_empezar():
    assert motor().build(None)[0].kind == "start"
    assert motor().build(StudentProfile.create(uuid4()))[0].kind == "start"


@pytest.mark.parametrize("veces", [1, 2, 5])
def test_la_lista_nunca_pasa_de_diez(veces):
    profile = perfil_que_falla(
        "funciones", "ecuacion", "variable", "derivadas", "matrices", veces=veces
    )

    assert len(motor().build(profile)) <= 10
