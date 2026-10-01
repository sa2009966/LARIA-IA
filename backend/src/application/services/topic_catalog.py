"""El tema canónico de lo que escribe el estudiante (ADR-017, ADR-022)."""
from __future__ import annotations

from src.domain.catalog.prerequisite_seeds import build_seeded_graph
from src.domain.concept_identity import canonicalize_concept
from src.domain.ports.repositories import ConceptGraphRepository


class TopicCatalog:
    """Resuelve "ecuaciones" a "ecuaciones lineales", la clave con que se guarda el nivel.

    Lo usa el chat sin material para encontrar el nivel que dejó la nivelación:
    buscando por lo escrito no lo encontraría, igual que le pasaba al diagnóstico.
    """

    def __init__(
        self, graph_repository: ConceptGraphRepository | None = None, graph_id: str = "default"
    ) -> None:
        self._repo = graph_repository
        self._graph_id = graph_id
        self._graph = None

    async def graph(self):
        if self._graph is None:
            if self._repo is not None:
                self._graph = await self._repo.find_by_id(self._graph_id)
            if self._graph is None:
                self._graph = build_seeded_graph(self._graph_id)
        return self._graph

    async def canonical(self, topic: str) -> str:
        if self._graph is None:
            if self._repo is not None:
                self._graph = await self._repo.find_by_id(self._graph_id)
            if self._graph is None:
                self._graph = build_seeded_graph(self._graph_id)
        return self._graph.canonicalize(canonicalize_concept(topic))
