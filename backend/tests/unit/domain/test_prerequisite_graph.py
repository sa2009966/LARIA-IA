"""API pública del grafo de prerrequisitos (sin leer _edges desde fuera)."""
from src.domain.services.prerequisite_graph import PrerequisiteGraph


def test_successors_of_is_inverse_of_prerequisites_of():
    graph = PrerequisiteGraph()
    assert "derivadas" in graph.successors_of("funciones")
    samples = (
        "variable",
        "expresión algebraica",
        "ecuación",
        "funciones",
        "derivadas",
        "integrales",
        "propiedad distributiva",
    )
    for concept in samples:
        canon = graph.canonicalize(concept)
        for successor in graph.successors_of(concept):
            assert canon in graph.prerequisites_of(successor)


def test_successors_of_respects_aliases():
    graph = PrerequisiteGraph()
    via_alias = graph.successors_of("función")
    via_canon = graph.successors_of("funciones")
    assert via_alias == via_canon
    assert "derivadas" in via_alias
    assert "integrales" in via_alias
