"""Semillas curriculares del grafo de prerrequisitos (ADR-005).

Son **datos**, no lógica: el currículum del dominio piloto (álgebra, cálculo,
física) que se siembra en el agregado `ConceptGraph` como aristas `CURATED`.
Una vez sembrado, el grafo se edita por curación, no editando este archivo.
"""
from __future__ import annotations

from src.domain.aggregates.concept_graph import ConceptGraph

#: concepto → prerrequisitos directos.
SEED_EDGES: dict[str, tuple[str, ...]] = {
    # Álgebra
    "expresión algebraica": ("variable",),
    "propiedad distributiva": ("expresión algebraica", "variable"),
    "ecuación": ("variable", "expresión algebraica"),
    "ecuaciones lineales": ("ecuación", "variable"),
    "sistemas": ("ecuaciones lineales", "ecuación"),
    "sistemas de ecuaciones": ("ecuaciones lineales",),
    "matrices": ("sistemas", "ecuaciones lineales"),
    "desigualdad": ("ecuación", "variable"),
    "resolver ecuación": ("ecuación", "variable"),
    "términos semejantes": ("variable", "expresión algebraica"),
    "factorización": ("propiedad distributiva", "expresión algebraica"),
    "ecuación cuadrática": ("ecuación", "factorización"),
    # Cálculo
    "funciones": ("variable", "expresión algebraica"),
    "derivadas": ("funciones",),
    "integrales": ("derivadas", "funciones"),
    # Física
    "mru": ("funciones",),
    "cinemática": ("mru",),
    "dinámica": ("cinemática",),
}

#: Alias → clave canónica del grafo.
SEED_ALIASES: dict[str, str] = {
    "ecuaciones": "ecuaciones lineales",
    "sistema": "sistemas",
    "matriz": "matrices",
    "derivada": "derivadas",
    "integral": "integrales",
    "función": "funciones",
    "funcion": "funciones",
    "distributiva": "propiedad distributiva",
    "álgebra": "variable",
    "algebra": "variable",
    "despejar": "resolver ecuación",
    "cuadrática": "ecuación cuadrática",
    "cuadratica": "ecuación cuadrática",
    "factorizar": "factorización",
    "términos": "términos semejantes",
    "terminos": "términos semejantes",
}


def build_seeded_graph(graph_id: str = "default") -> ConceptGraph:
    """Grafo con el currículum piloto ya curado."""
    graph = ConceptGraph(graph_id=graph_id, aliases=dict(SEED_ALIASES))
    for concept, prerequisites in SEED_EDGES.items():
        for prerequisite in prerequisites:
            graph.curate(concept, prerequisite)
    return graph
