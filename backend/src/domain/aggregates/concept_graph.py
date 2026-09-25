"""Grafo de prerrequisitos entre conceptos (ADR-005).

Agregado con ciclo de vida propio: curación docente, sugerencias inferidas,
aprobación y versionado. Dos invariantes que el agregado garantiza:

1. **Es un DAG.** Toda escritura que cerraría un ciclo se rechaza. Un ciclo no
   es solo un problema de recorrido: es un currículum sin entrada posible.
2. **Solo lo curado bloquea.** Una arista `INFERRED` (correlación, orden de un
   PDF) se guarda como sugerencia y no gatea a nadie hasta que un humano la
   aprueba.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from src.domain.concept_identity import canonicalize_concept


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _norm(label: str) -> str:
    return canonicalize_concept(label)


class CyclicPrerequisiteError(ValueError):
    """La arista cerraría un ciclo: dejaría el currículum sin punto de entrada."""


class EdgeSource(str, Enum):
    CURATED = "curated"  # docente/curador o semilla revisada: puede bloquear
    INFERRED = "inferred"  # correlación/orden de documento: nunca bloquea


@dataclass(frozen=True)
class ConceptEdge:
    """`prerequisite` habilita a `concept`: hay que dominarlo antes."""

    concept: str
    prerequisite: str
    source: EdgeSource = EdgeSource.CURATED
    confidence: float = 1.0


@dataclass
class ConceptGraph:
    """Mapa del conocimiento: qué concepto habilita a qué otro."""

    graph_id: str = "default"
    edges: list[ConceptEdge] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=_utc_now)
    version: int = 0

    def __post_init__(self) -> None:
        # Las claves de alias se pliegan al entrar. La búsqueda de
        # `canonicalize()` siempre usa la clave plegada, así que un alias
        # guardado con tilde ("límites") nunca se encontraría y quedaría muerto
        # sin avisar. Plegarlo aquí cubre la semilla, lo que cura un docente y
        # lo que vuelve de la base de datos.
        self.aliases = {_norm(k): v for k, v in self.aliases.items() if _norm(k)}

    # --- Identidad de conceptos ---------------------------------------------------

    def canonicalize(self, concept: str) -> str:
        key = _norm(concept)
        alias = self.aliases.get(key)
        return _norm(alias) if alias else key

    # --- Escritura (invariante DAG) -----------------------------------------------

    def curate(self, concept: str, prerequisite: str) -> ConceptEdge | None:
        """Declara una arista como verdad curricular. Puede bloquear.

        Levanta si cerraría un ciclo: es una acción deliberada y quien la hace
        necesita enterarse.
        """
        edge = self._build_edge(concept, prerequisite, EdgeSource.CURATED, 1.0)
        if edge is None:
            return None
        if self._would_cycle(edge):
            raise CyclicPrerequisiteError(
                f"'{edge.prerequisite}' ya depende de '{edge.concept}': "
                "la arista cerraría un ciclo."
            )
        return self._upsert(edge)

    def suggest(
        self, concept: str, prerequisite: str, confidence: float = 0.5
    ) -> ConceptEdge | None:
        """Propone una arista inferida. No bloquea a nadie hasta `approve()`.

        A diferencia de `curate()`, un ciclo se descarta en silencio: la
        sugerencia es automática y no hay usuario a quien reportarle nada.
        """
        edge = self._build_edge(
            concept, prerequisite, EdgeSource.INFERRED, confidence
        )
        if edge is None or self._would_cycle(edge):
            return None
        existing = self._find(edge.concept, edge.prerequisite)
        if existing is not None:
            # Nunca degradar una arista ya curada a sugerencia.
            return existing
        return self._upsert(edge)

    def approve(self, concept: str, prerequisite: str) -> ConceptEdge | None:
        """Convierte una sugerencia en verdad curricular."""
        existing = self._find(self.canonicalize(concept), self.canonicalize(prerequisite))
        if existing is None:
            return None
        return self._upsert(
            ConceptEdge(
                concept=existing.concept,
                prerequisite=existing.prerequisite,
                source=EdgeSource.CURATED,
                confidence=1.0,
            )
        )

    def remove(self, concept: str, prerequisite: str) -> bool:
        target = (self.canonicalize(concept), self.canonicalize(prerequisite))
        before = len(self.edges)
        self.edges = [
            e for e in self.edges if (e.concept, e.prerequisite) != target
        ]
        if len(self.edges) != before:
            self.updated_at = _utc_now()
            return True
        return False

    def suggest_from_document_order(self, concepts: tuple[str, ...]) -> int:
        """El orden de aparición en un documento sugiere una cadena débil.

        Señal barata y ruidosa: entra como `INFERRED` y no gatea. Devuelve
        cuántas sugerencias nuevas se añadieron.
        """
        keys = [self.canonicalize(c) for c in concepts if c and c.strip()]
        added = 0
        for earlier, later in zip(keys, keys[1:]):
            if earlier == later:
                continue
            if self._find(later, earlier) is not None:
                continue
            if self.suggest(later, earlier, confidence=0.3) is not None:
                added += 1
        return added

    # --- Lectura ------------------------------------------------------------------

    def prerequisites_of(
        self, concept: str, *, curated_only: bool = True
    ) -> tuple[str, ...]:
        key = self.canonicalize(concept)
        return tuple(
            e.prerequisite
            for e in self.edges
            if e.concept == key and self._counts(e, curated_only)
        )

    def successors_of(
        self, concept: str, *, curated_only: bool = True
    ) -> tuple[str, ...]:
        """Conceptos que dependen de `concept` (inverso de `prerequisites_of`)."""
        key = self.canonicalize(concept)
        return tuple(
            dict.fromkeys(
                e.concept
                for e in self.edges
                if e.prerequisite == key and self._counts(e, curated_only)
            )
        )

    def all_prerequisites(
        self, concept: str, *, curated_only: bool = True
    ) -> tuple[str, ...]:
        """Cierre transitivo en orden topológico inverso: bases primero."""
        key = self.canonicalize(concept)
        ordered: list[str] = []
        visiting: set[str] = set()

        def walk(node: str) -> None:
            if node in visiting:
                return
            visiting.add(node)
            for pre in self.prerequisites_of(node, curated_only=curated_only):
                walk(pre)
                if pre not in ordered:
                    ordered.append(pre)
            visiting.discard(node)

        walk(key)
        return tuple(ordered)

    def suggestions(self) -> tuple[ConceptEdge, ...]:
        """Aristas inferidas pendientes de aprobación humana."""
        return tuple(e for e in self.edges if e.source == EdgeSource.INFERRED)

    def concepts(self) -> tuple[str, ...]:
        nodes: list[str] = []
        for edge in self.edges:
            for node in (edge.prerequisite, edge.concept):
                if node not in nodes:
                    nodes.append(node)
        return tuple(nodes)

    def root_causes(self, gaps: tuple[str, ...]) -> tuple[str, ...]:
        """De un conjunto de huecos, los más upstream (ADR-005, Decisión 4).

        Un hueco es raíz si ninguno de sus propios prerrequisitos está también
        en el conjunto. Remediar la raíz ataca la causa; remediar el resto
        trata el síntoma.

        Siendo el grafo un DAG, un conjunto no vacío siempre tiene al menos una
        raíz: la de menor orden topológico.
        """
        pending = set(gaps)
        return tuple(
            gap for gap in gaps if not (set(self.all_prerequisites(gap)) & pending)
        )

    # --- Internos -----------------------------------------------------------------

    def _build_edge(
        self, concept: str, prerequisite: str, source: EdgeSource, confidence: float
    ) -> ConceptEdge | None:
        target = self.canonicalize(concept)
        pre = self.canonicalize(prerequisite)
        if not target or not pre or target == pre:
            return None
        return ConceptEdge(
            concept=target,
            prerequisite=pre,
            source=source,
            confidence=max(0.0, min(1.0, float(confidence))),
        )

    def _would_cycle(self, edge: ConceptEdge) -> bool:
        """¿`edge.concept` ya es prerrequisito transitivo de `edge.prerequisite`?"""
        if edge.concept == edge.prerequisite:
            return True
        ancestors = self.all_prerequisites(edge.prerequisite, curated_only=False)
        return edge.concept in ancestors

    def _find(self, concept: str, prerequisite: str) -> ConceptEdge | None:
        for edge in self.edges:
            if edge.concept == concept and edge.prerequisite == prerequisite:
                return edge
        return None

    def _upsert(self, edge: ConceptEdge) -> ConceptEdge:
        self.edges = [
            e
            for e in self.edges
            if (e.concept, e.prerequisite) != (edge.concept, edge.prerequisite)
        ]
        self.edges.append(edge)
        self.updated_at = _utc_now()
        return edge

    @staticmethod
    def _counts(edge: ConceptEdge, curated_only: bool) -> bool:
        return not curated_only or edge.source == EdgeSource.CURATED
