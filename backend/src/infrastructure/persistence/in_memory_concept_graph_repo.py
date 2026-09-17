from typing import Optional

from src.domain.aggregates.concept_graph import ConceptGraph
from src.domain.exceptions import ConcurrencyError
from src.domain.ports.repositories import ConceptGraphRepository


def _clone(graph: ConceptGraph, version: int | None = None) -> ConceptGraph:
    return ConceptGraph(
        graph_id=graph.graph_id,
        # ConceptEdge es frozen: copiar la lista basta para aislar el agregado.
        edges=list(graph.edges),
        aliases=dict(graph.aliases),
        updated_at=graph.updated_at,
        version=graph.version if version is None else version,
    )


class InMemoryConceptGraphRepository(ConceptGraphRepository):

    def __init__(self) -> None:
        self._graphs: dict[str, ConceptGraph] = {}

    async def find_by_id(self, graph_id: str) -> Optional[ConceptGraph]:
        graph = self._graphs.get(graph_id)
        return _clone(graph) if graph is not None else None

    async def save(self, graph: ConceptGraph) -> None:
        existing = self._graphs.get(graph.graph_id)
        expected = int(graph.version)
        if existing is not None and existing.version != expected:
            raise ConcurrencyError("ConceptGraph concurrent update")
        if existing is None and expected != 0:
            raise ConcurrencyError("ConceptGraph concurrent update")
        new_version = expected + 1
        self._graphs[graph.graph_id] = _clone(graph, version=new_version)
        graph.version = new_version
