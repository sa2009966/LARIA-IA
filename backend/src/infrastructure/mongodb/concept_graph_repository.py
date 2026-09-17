from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.domain.aggregates.concept_graph import ConceptEdge, ConceptGraph, EdgeSource
from src.domain.exceptions import ConcurrencyError
from src.domain.ports.repositories import ConceptGraphRepository
from src.infrastructure.mongodb.database import get_database


class MongoDBConceptGraphRepository(ConceptGraphRepository):

    def __init__(self, database: Optional[AsyncIOMotorDatabase] = None) -> None:
        self._database = database

    async def _get_db(self) -> AsyncIOMotorDatabase:
        if self._database is None:
            self._database = await get_database()
        return self._database

    @staticmethod
    def _to_doc(graph: ConceptGraph, version: int) -> dict:
        return {
            "_id": graph.graph_id,
            "graph_id": graph.graph_id,
            "edges": [
                {
                    "concept": e.concept,
                    "prerequisite": e.prerequisite,
                    "source": e.source.value,
                    "confidence": e.confidence,
                }
                for e in graph.edges
            ],
            "aliases": dict(graph.aliases),
            "updated_at": graph.updated_at,
            "version": version,
        }

    @staticmethod
    def _from_doc(doc: dict) -> ConceptGraph:
        edges: list[ConceptEdge] = []
        for raw in doc.get("edges") or []:
            try:
                source = EdgeSource(raw.get("source", EdgeSource.CURATED.value))
            except ValueError:
                # Procedencia desconocida: tratar como sugerencia, nunca como
                # verdad que pueda bloquear a un estudiante (ADR-005).
                source = EdgeSource.INFERRED
            edges.append(
                ConceptEdge(
                    concept=raw["concept"],
                    prerequisite=raw["prerequisite"],
                    source=source,
                    confidence=float(raw.get("confidence", 1.0)),
                )
            )
        return ConceptGraph(
            graph_id=doc.get("graph_id", doc["_id"]),
            edges=edges,
            aliases=dict(doc.get("aliases") or {}),
            updated_at=doc["updated_at"],
            version=int(doc.get("version", 0)),
        )

    async def find_by_id(self, graph_id: str) -> Optional[ConceptGraph]:
        db = await self._get_db()
        doc = await db.concept_graphs.find_one({"_id": graph_id})
        return self._from_doc(doc) if doc else None

    async def save(self, graph: ConceptGraph) -> None:
        db = await self._get_db()
        expected = int(graph.version)
        new_version = expected + 1
        payload = self._to_doc(graph, new_version)
        _id = payload["_id"]
        if expected == 0:
            existing = await db.concept_graphs.find_one({"_id": _id}, projection={"version": 1})
            if existing is None:
                await db.concept_graphs.insert_one(payload)
            else:
                result = await db.concept_graphs.replace_one(
                    {
                        "_id": _id,
                        "$or": [{"version": 0}, {"version": {"$exists": False}}],
                    },
                    payload,
                )
                if result.matched_count == 0:
                    raise ConcurrencyError("ConceptGraph concurrent update")
        else:
            result = await db.concept_graphs.replace_one(
                {"_id": _id, "version": expected},
                payload,
            )
            if result.matched_count == 0:
                raise ConcurrencyError("ConceptGraph concurrent update")
        graph.version = new_version
