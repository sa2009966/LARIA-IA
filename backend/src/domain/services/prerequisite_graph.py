"""Gate de prerrequisitos: la intervención escala con la evidencia (ADR-006).

El grafo no vive aquí. Este servicio es sin estado: recibe el agregado
`ConceptGraph` cargado y el perfil, y responde **con qué fuerza** intervenir.

Invariante: nunca se desvía el foco en silencio. Solo `SEQUENCE` lidera con la
base, y cuando lo hace el prompt explica por qué. Solo las aristas curadas
pueden llegar a `SEQUENCE` (ADR-005).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.domain.aggregates.concept_graph import ConceptGraph
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.catalog.prerequisite_seeds import build_seeded_graph


class GateAction(str, Enum):
    PROCEED = "proceed"  # bases dominadas (o sin bases): responder y avanzar
    INTEGRATE = "integrate"  # hueco NO medido: responder apoyándose en la base
    OFFER = "offer"  # hueco medido: responder y ofrecer repasar la base
    SEQUENCE = "sequence"  # hueco medido y repetido: liderar con la base


@dataclass(frozen=True)
class GateResult:
    action: GateAction
    target: str
    missing_prereqs: tuple[str, ...]
    remediation_focus: tuple[str, ...]
    measured_gaps: tuple[str, ...] = ()

    @property
    def blocked(self) -> bool:
        """El turno lidera con la base. NO significa "hay huecos"."""
        return self.action == GateAction.SEQUENCE


class PrerequisiteGate:
    """Decide la fuerza de la intervención según la evidencia disponible."""

    def __init__(
        self,
        graph: ConceptGraph | None = None,
        min_mastery: float = 0.45,
        max_remediation: int = 4,
        min_evidence_for_gap: int = 2,
        error_streak_for_sequence: int = 2,
    ) -> None:
        # El grafo por defecto es la semilla curricular; en producción la capa
        # de aplicación pasa el agregado persistido en cada evaluación.
        self._graph = graph or build_seeded_graph()
        self._min_mastery = min_mastery
        self._max_remediation = max_remediation
        # Hipótesis nombradas, como los cutoffs del ADR-004: cuánta evidencia
        # exige llamar "hueco" a un prerrequisito, y cuánta insistir en él.
        self._min_evidence_for_gap = min_evidence_for_gap
        self._error_streak_for_sequence = error_streak_for_sequence

    @property
    def graph(self) -> ConceptGraph:
        return self._graph

    def evaluate(
        self,
        target: str,
        profile: StudentProfile | None,
        *,
        min_mastery: float | None = None,
        graph: ConceptGraph | None = None,
    ) -> GateResult:
        active = graph or self._graph
        threshold = self._min_mastery if min_mastery is None else min_mastery
        canon = active.canonicalize(target)
        prereqs = active.all_prerequisites(canon)
        if not prereqs:
            return GateResult(GateAction.PROCEED, canon, (), ())

        # Distinguir "no medido" de "medido bajo" es toda la decisión del
        # ADR-006: la ausencia de dato no es evidencia de ignorancia.
        unmeasured: list[str] = []
        measured: list[str] = []
        insistent: list[str] = []
        for pre in prereqs:
            entry = None if profile is None else profile.mastery_by_concept.get(pre)
            # El mastery suficiente se respeta primero: el umbral de evidencia
            # decide si algo ES un hueco, no invalida un nivel que ya pasa.
            if entry is not None and profile.effective_concept_mastery(pre) >= threshold:
                continue
            if entry is None or entry.evidence_count < self._min_evidence_for_gap:
                unmeasured.append(pre)
                continue
            measured.append(pre)
            if entry.error_streak >= self._error_streak_for_sequence:
                insistent.append(pre)

        if not unmeasured and not measured:
            return GateResult(GateAction.PROCEED, canon, (), ())

        if insistent:
            action = GateAction.SEQUENCE
            focus_pool = tuple(insistent)
        elif measured:
            action = GateAction.OFFER
            focus_pool = tuple(measured)
        else:
            action = GateAction.INTEGRATE
            focus_pool = tuple(unmeasured)

        missing = tuple(p for p in prereqs if p in set(unmeasured) | set(measured))
        # Remediar la causa raíz, no el primer hueco del recorrido: si faltan
        # `variable` y `ecuaciones lineales`, atender lo segundo sin lo primero
        # solo trata el síntoma.
        remediation = active.root_causes(focus_pool)[: self._max_remediation]
        return GateResult(action, canon, missing, remediation, tuple(measured))
