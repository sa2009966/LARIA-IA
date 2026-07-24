"""Grafo de prerrequisitos curriculares (determinista, sin LLM)."""
from __future__ import annotations

from dataclasses import dataclass

from src.domain.aggregates.student_profile import StudentProfile


def _norm(label: str) -> str:
    return label.strip().lower()


# concepto → lista de prerrequisitos directos
_DEFAULT_EDGES: dict[str, tuple[str, ...]] = {
    # Álgebra
    "variable": (),
    "expresión algebraica": ("variable",),
    "propiedad distributiva": ("expresión algebraica", "variable"),
    "ecuación": ("variable", "expresión algebraica"),
    "ecuaciones lineales": ("ecuación", "variable"),
    "sistemas": ("ecuaciones lineales", "ecuación"),
    "sistemas de ecuaciones": ("ecuaciones lineales",),
    "matrices": ("sistemas", "ecuaciones lineales"),
    "desigualdad": ("ecuación", "variable"),
    "resolver ecuación": ("ecuación", "variable"),
    # Cálculo
    "funciones": ("variable", "expresión algebraica"),
    "derivadas": ("funciones",),
    "integrales": ("derivadas", "funciones"),
    # Física
    "mru": ("funciones",),
    "cinemática": ("mru",),
    "dinámica": ("cinemática",),
}

# Alias → clave canónica del grafo
_ALIASES: dict[str, str] = {
    "ecuacion": "ecuación",
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
}


@dataclass(frozen=True)
class GateResult:
    blocked: bool
    target: str
    missing_prereqs: tuple[str, ...]
    remediation_focus: tuple[str, ...]


class PrerequisiteGraph:
    """Semillas curriculares + resolución de cadenas de prerrequisitos."""

    def __init__(self, edges: dict[str, tuple[str, ...]] | None = None) -> None:
        self._edges = { _norm(k): tuple(_norm(p) for p in v) for k, v in (edges or _DEFAULT_EDGES).items() }

    def canonicalize(self, concept: str) -> str:
        key = _norm(concept)
        return _ALIASES.get(key, key)

    def prerequisites_of(self, concept: str) -> tuple[str, ...]:
        key = self.canonicalize(concept)
        return self._edges.get(key, ())

    def all_prerequisites(self, concept: str) -> tuple[str, ...]:
        """DFS transitivo, orden topológico inverso (bases primero)."""
        key = self.canonicalize(concept)
        seen: list[str] = []
        stack = [key]
        visiting: set[str] = set()

        def walk(node: str) -> None:
            node = self.canonicalize(node)
            if node in visiting:
                return
            visiting.add(node)
            for pre in self._edges.get(node, ()):
                walk(pre)
                if pre not in seen:
                    seen.append(pre)
            visiting.discard(node)

        walk(key)
        return tuple(seen)

    def extend_with_document_concepts(self, concepts: tuple[str, ...]) -> None:
        """Heurística ligera: orden del documento sugiere cadena lineal débil."""
        norms = [self.canonicalize(c) for c in concepts if c and c.strip()]
        for i in range(1, len(norms)):
            later = norms[i]
            earlier = norms[i - 1]
            if later == earlier:
                continue
            existing = list(self._edges.get(later, ()))
            if earlier not in existing:
                existing.append(earlier)
                self._edges[later] = tuple(existing)
            self._edges.setdefault(earlier, self._edges.get(earlier, ()))


class PrerequisiteGate:
    """Bloquea temas avanzados si faltan bases (umbral de mastery efectivo)."""

    def __init__(
        self,
        graph: PrerequisiteGraph | None = None,
        min_mastery: float = 0.45,
    ) -> None:
        self._graph = graph or PrerequisiteGraph()
        self._min_mastery = min_mastery

    @property
    def graph(self) -> PrerequisiteGraph:
        return self._graph

    def evaluate(
        self,
        target: str,
        profile: StudentProfile | None,
        *,
        min_mastery: float | None = None,
    ) -> GateResult:
        threshold = self._min_mastery if min_mastery is None else min_mastery
        canon = self._graph.canonicalize(target)
        prereqs = self._graph.all_prerequisites(canon)
        if not prereqs:
            return GateResult(False, canon, (), ())

        missing: list[str] = []
        for pre in prereqs:
            if profile is None:
                missing.append(pre)
                continue
            mastery = profile.effective_concept_mastery(pre)
            known = pre in profile.mastery_by_concept
            if not known or mastery < threshold:
                missing.append(pre)

        if not missing:
            return GateResult(False, canon, (), ())

        # Remediation: los prerrequisitos más básicos primero (ya en orden)
        remediation = tuple(missing[:4])
        return GateResult(True, canon, tuple(missing), remediation)
