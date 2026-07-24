"""Motor de recomendaciones pedagógicas."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.domain.aggregates.student_profile import StudentProfile
from src.domain.services.prerequisite_graph import PrerequisiteGate


@dataclass(frozen=True)
class LearningRecommendation:
    kind: str
    message: str
    document_id: UUID | None = None
    concept: str | None = None
    priority: float = 0.0
    suggested_minutes: int | None = None


class RecommendationEngine:
    def __init__(self, gate: PrerequisiteGate | None = None) -> None:
        self._gate = gate or PrerequisiteGate()

    def build(self, profile: StudentProfile | None) -> list[LearningRecommendation]:
        if profile is None or (
            not profile.mastery_by_document and not profile.mastery_by_concept
        ):
            return [
                LearningRecommendation(
                    kind="start",
                    message="Comienza con un quiz fácil sobre tu documento para medir tu nivel.",
                    priority=1.0,
                    suggested_minutes=15,
                )
            ]

        recs: list[LearningRecommendation] = []

        # Forgotten
        for concept in profile.forgotten_concepts(limit=3):
            gap = profile.mastery_by_concept[concept].forgetting_gap()
            minutes = int(10 + 20 * gap)
            recs.append(
                LearningRecommendation(
                    kind="forgotten",
                    message=f"Repasa antes de que se olvide: {concept}.",
                    concept=concept,
                    priority=0.9 + gap,
                    suggested_minutes=minutes,
                )
            )

        # Pending (nunca o poco practicado)
        pending = sorted(
            profile.mastery_by_concept.values(),
            key=lambda c: (c.attempts, c.effective_mastery()),
        )
        for c in pending[:3]:
            if c.attempts <= 1 and c.effective_mastery() < 0.6:
                recs.append(
                    LearningRecommendation(
                        kind="pending",
                        message=f"Concepto pendiente de consolidar: {c.concept_key}.",
                        concept=c.concept_key,
                        priority=0.75,
                        suggested_minutes=12,
                    )
                )

        # Review priority / weak
        for concept in profile.weakest_concepts(limit=4, use_effective=True):
            mastery = profile.effective_concept_mastery(concept)
            if mastery >= 0.5:
                continue
            entry = profile.mastery_by_concept.get(concept)
            conf = entry.confidence if entry else 0.0
            blocker = 1.2 if self._is_blocking_prereq(concept, profile) else 1.0
            priority = (1.0 - mastery) * (1.1 - 0.3 * conf) * blocker
            recs.append(
                LearningRecommendation(
                    kind="review_priority",
                    message=f"Prioridad de repaso: {concept}.",
                    concept=concept,
                    priority=priority,
                    suggested_minutes=int(8 + 25 * (1.0 - mastery)),
                )
            )
            recs.append(
                LearningRecommendation(
                    kind="review_concept",
                    message=f"Repasa: {concept}.",
                    concept=concept,
                    priority=priority * 0.95,
                    suggested_minutes=int(8 + 20 * (1.0 - mastery)),
                )
            )

        # Next topic (prereqs OK, mastery medio)
        for key, cm in profile.mastery_by_concept.items():
            eff = cm.effective_mastery()
            if not (0.45 <= eff < 0.75):
                continue
            gate = self._gate.evaluate(key, profile)
            if gate.blocked:
                continue
            # Buscar un sucesor en el grafo
            successor = self._find_ready_successor(key, profile)
            if successor:
                recs.append(
                    LearningRecommendation(
                        kind="next_topic",
                        message=f"Siguiente tema recomendado: {successor}.",
                        concept=successor,
                        priority=0.7,
                        suggested_minutes=20,
                    )
                )
                break

        # Mastered
        for concept in profile.mastered_concepts(limit=3):
            recs.append(
                LearningRecommendation(
                    kind="mastered",
                    message=f"Dominado: {concept}. Puedes avanzar o enseñarlo a otros.",
                    concept=concept,
                    priority=0.2,
                    suggested_minutes=5,
                )
            )

        # Study time aggregate
        top = sorted(recs, key=lambda r: r.priority, reverse=True)[:3]
        if top:
            total_min = sum(r.suggested_minutes or 10 for r in top)
            recs.append(
                LearningRecommendation(
                    kind="study_time",
                    message=f"Tiempo sugerido de estudio hoy: ~{total_min} minutos.",
                    priority=0.55,
                    suggested_minutes=total_min,
                )
            )

        # Document-level fallbacks
        for doc_id in profile.weakest_documents(limit=2):
            mastery = profile.mastery_for(doc_id)
            if mastery < 0.4:
                recs.append(
                    LearningRecommendation(
                        kind="review",
                        message="Repasa el documento con explicación guiada (andamiaje).",
                        document_id=doc_id,
                        priority=0.65,
                        suggested_minutes=15,
                    )
                )
                recs.append(
                    LearningRecommendation(
                        kind="easier_quiz",
                        message="Haz un quiz más fácil para consolidar lo básico.",
                        document_id=doc_id,
                        priority=0.6,
                        suggested_minutes=12,
                    )
                )
            elif mastery < 0.7:
                recs.append(
                    LearningRecommendation(
                        kind="guided_explain",
                        message="Pide una explicación guiada de los puntos débiles.",
                        document_id=doc_id,
                        priority=0.5,
                        suggested_minutes=10,
                    )
                )
            else:
                recs.append(
                    LearningRecommendation(
                        kind="challenge",
                        message="Practica con un quiz más exigente o preguntas socráticas.",
                        document_id=doc_id,
                        priority=0.4,
                        suggested_minutes=15,
                    )
                )

        # Deduplicate by (kind, concept, document), keep highest priority
        best: dict[tuple, LearningRecommendation] = {}
        for r in recs:
            key = (r.kind, r.concept, r.document_id)
            prev = best.get(key)
            if prev is None or r.priority > prev.priority:
                best[key] = r
        return sorted(best.values(), key=lambda x: x.priority, reverse=True)[:10]

    def _is_blocking_prereq(self, concept: str, profile: StudentProfile) -> bool:
        # Si otros conceptos lo requieren y está débil, es bloqueante
        for other in profile.mastery_by_concept:
            gate = self._gate.evaluate(other, profile)
            if concept in gate.missing_prereqs:
                return True
        return False

    def _find_ready_successor(self, concept: str, profile: StudentProfile) -> str | None:
        graph = self._gate.graph
        canon = graph.canonicalize(concept)
        for candidate, prereqs in graph._edges.items():  # noqa: SLF001 — lectura intencional del grafo
            if canon in prereqs:
                gate = self._gate.evaluate(candidate, profile)
                if not gate.blocked and profile.effective_concept_mastery(candidate) < 0.7:
                    return candidate
        return None
