"""Invariantes del agregado ConceptGraph (ADR-005).

Blindan las cuatro decisiones: agregado con ciclo de vida, procedencia (solo lo
curado bloquea), DAG validado en escritura y remediación a la causa raíz.
"""
import pytest

from src.domain.aggregates.concept_graph import (
    ConceptGraph,
    CyclicPrerequisiteError,
    EdgeSource,
)
from src.domain.catalog.prerequisite_seeds import build_seeded_graph


# --- Decisión 3: invariante DAG -----------------------------------------------------


def test_curar_un_ciclo_directo_levanta():
    graph = ConceptGraph()
    graph.curate("ecuación", "variable")
    with pytest.raises(CyclicPrerequisiteError):
        graph.curate("variable", "ecuación")


def test_curar_un_ciclo_transitivo_levanta():
    graph = ConceptGraph()
    graph.curate("b", "a")
    graph.curate("c", "b")
    with pytest.raises(CyclicPrerequisiteError):
        graph.curate("a", "c")


def test_autoarista_se_descarta():
    graph = ConceptGraph()
    assert graph.curate("variable", "variable") is None
    assert graph.edges == []


def test_sugerencia_ciclica_se_descarta_en_silencio():
    """La sugerencia es automática: no hay usuario a quien reportarle nada."""
    graph = ConceptGraph()
    graph.curate("b", "a")
    assert graph.suggest("a", "b") is None
    assert len(graph.edges) == 1


def test_el_ciclo_se_evalua_sobre_todas_las_aristas():
    """Una sugerencia previa también cuenta para detectar el ciclo."""
    graph = ConceptGraph()
    graph.suggest("b", "a")
    with pytest.raises(CyclicPrerequisiteError):
        graph.curate("a", "b")


def test_la_semilla_curricular_es_un_dag():
    graph = build_seeded_graph()
    for concept in graph.concepts():
        assert concept not in graph.all_prerequisites(concept, curated_only=False)


# --- Decisión 2: procedencia --------------------------------------------------------


def test_curada_cuenta_para_gatear_y_sugerida_no():
    graph = ConceptGraph()
    graph.curate("ecuación", "variable")
    graph.suggest("ecuación", "pobreza")

    assert graph.prerequisites_of("ecuación") == ("variable",)
    assert set(graph.prerequisites_of("ecuación", curated_only=False)) == {
        "variable",
        "pobreza",
    }


def test_sugerencias_quedan_pendientes_de_aprobacion():
    graph = ConceptGraph()
    graph.suggest("ecuación", "variable", confidence=0.3)

    pendientes = graph.suggestions()
    assert len(pendientes) == 1
    assert pendientes[0].source == EdgeSource.INFERRED
    assert pendientes[0].confidence == 0.3


def test_aprobar_convierte_la_sugerencia_en_verdad():
    graph = ConceptGraph()
    graph.suggest("ecuación", "variable")
    assert graph.prerequisites_of("ecuación") == ()

    graph.approve("ecuación", "variable")

    assert graph.prerequisites_of("ecuación") == ("variable",)
    assert graph.suggestions() == ()


def test_sugerir_no_degrada_una_arista_ya_curada():
    graph = ConceptGraph()
    graph.curate("ecuación", "variable")
    graph.suggest("ecuación", "variable", confidence=0.1)

    assert graph.prerequisites_of("ecuación") == ("variable",)
    assert graph.suggestions() == ()


def test_orden_del_documento_solo_produce_sugerencias():
    """El orden de maquetación de un PDF no puede bloquear a un estudiante."""
    graph = ConceptGraph()
    added = graph.suggest_from_document_order(("pobreza", "desigualdad social", "gini"))

    assert added == 2
    assert all(e.source == EdgeSource.INFERRED for e in graph.edges)
    assert graph.prerequisites_of("gini") == ()


def test_orden_del_documento_es_idempotente():
    graph = ConceptGraph()
    concepts = ("pobreza", "desigualdad social")
    assert graph.suggest_from_document_order(concepts) == 1
    assert graph.suggest_from_document_order(concepts) == 0


def test_remover_borra_la_arista():
    graph = ConceptGraph()
    graph.curate("ecuación", "variable")
    assert graph.remove("ecuación", "variable") is True
    assert graph.remove("ecuación", "variable") is False
    assert graph.prerequisites_of("ecuación") == ()


# --- Decisión 4: causa raíz ---------------------------------------------------------


def test_root_causes_devuelve_lo_mas_upstream():
    graph = build_seeded_graph()
    gaps = ("variable", "ecuación", "ecuaciones lineales")

    assert graph.root_causes(gaps) == ("variable",)


def test_root_causes_admite_varias_raices_independientes():
    graph = ConceptGraph()
    graph.curate("c", "a")
    graph.curate("c", "b")

    assert set(graph.root_causes(("a", "b"))) == {"a", "b"}


def test_root_causes_siempre_devuelve_alguna_raiz():
    """Siendo un DAG, un conjunto no vacío nunca queda sin raíz."""
    graph = build_seeded_graph()
    for gaps in [
        ("matrices", "sistemas", "ecuaciones lineales", "ecuación", "variable"),
        ("integrales", "derivadas"),
        ("dinámica", "cinemática", "mru"),
    ]:
        assert graph.root_causes(gaps)


# --- Lectura -----------------------------------------------------------------------


def test_all_prerequisites_pone_las_bases_primero():
    graph = build_seeded_graph()
    cadena = graph.all_prerequisites("integrales")

    assert cadena.index("variable") < cadena.index("funciones")
    assert cadena.index("funciones") < cadena.index("derivadas")


def test_successors_of_es_el_inverso_de_prerequisites_of():
    graph = build_seeded_graph()
    for successor in graph.successors_of("funciones"):
        assert "funciones" in graph.prerequisites_of(successor)


def test_los_alias_se_pliegan_a_la_clave_canonica():
    graph = build_seeded_graph()
    assert graph.canonicalize("función") == graph.canonicalize("funciones")
    assert graph.successors_of("función") == graph.successors_of("funciones")
