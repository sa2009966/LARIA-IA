"""Motor de recomendaciones pedagógicas.

Tres reglas que este módulo garantiza, aprendidas al ejercitarlo por primera vez
con perfiles realistas (fase F):

1. **Un concepto aparece una sola vez.** Antes la deduplicación era por
   `(kind, concepto, documento)`, así que el mismo concepto salía como
   "olvidado", como "prioridad de repaso" y como "repasa" — tres filas que
   dicen lo mismo. Una lista de diez recomendaciones sobre tres conceptos no es
   una lista de diez recomendaciones.
2. **Lo que bloquea se dice, no se multiplica en silencio.** Un concepto débil
   que impide avanzar valía `×1.2` de prioridad y nada más; ahora se nombra lo
   que desbloquea, que es la única forma de que el estudiante entienda por qué
   se le pide repasar algo que no preguntó.
3. **El tiempo sugerido se calcula sobre la lista final.** Sumarlo antes de
   deduplicar contaba el mismo concepto varias veces e inflaba la cifra.
"""
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
            bloqueados = self._blocked_by(concept, profile)
            priority = (1.0 - mastery) * (1.1 - 0.3 * conf) * (1.2 if bloqueados else 1.0)
            minutos = int(8 + 25 * (1.0 - mastery))
            if bloqueados:
                recs.append(
                    LearningRecommendation(
                        kind="unblock",
                        message=(
                            f"Repasa {concept}: es lo que te está frenando en "
                            f"{', '.join(bloqueados)}."
                        ),
                        concept=concept,
                        priority=priority,
                        suggested_minutes=minutos,
                    )
                )
            else:
                recs.append(
                    LearningRecommendation(
                        kind="review_priority",
                        message=f"Prioridad de repaso: {concept}.",
                        concept=concept,
                        priority=priority,
                        suggested_minutes=minutos,
                    )
                )

        # Next topic (prereqs OK, mastery medio)
        for key, cm in profile.mastery_by_concept.items():
            eff = cm.effective_mastery()
            if not (0.45 <= eff < 0.75):
                continue
            gate = self._gate.evaluate(key, profile)
            # "Hay huecos" ya no es `blocked`: tras el ADR-006 eso significa
            # solo SEQUENCE. Frena un hueco MEDIDO; uno sin medir no, porque
            # ausencia de evidencia no es evidencia de carencia.
            if gate.measured_gaps:
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

        # Un concepto, una recomendación: la clave es el concepto, no el `kind`.
        # Con la clave anterior, "olvidado", "prioridad de repaso" y "repasa"
        # eran tres filas del mismo concepto y llenaban el tope de diez.
        best: dict[tuple, LearningRecommendation] = {}
        for r in recs:
            key = ("concept", r.concept) if r.concept else (r.kind, r.document_id)
            prev = best.get(key)
            if prev is None or r.priority > prev.priority:
                best[key] = r

        final = sorted(best.values(), key=lambda x: x.priority, reverse=True)[:9]
        if final:
            total_min = sum(r.suggested_minutes or 10 for r in final[:3])
            final.append(
                LearningRecommendation(
                    kind="study_time",
                    message=f"Tiempo sugerido de estudio hoy: ~{total_min} minutos.",
                    priority=0.55,
                    suggested_minutes=total_min,
                )
            )
        return sorted(final, key=lambda x: x.priority, reverse=True)

    def _blocked_by(self, concept: str, profile: StudentProfile) -> tuple[str, ...]:
        """Qué conceptos tiene este delante, y por tanto está frenando.

        Mira **hacia adelante en el grafo**, no solo entre lo que el estudiante
        ya ha tocado. Antes se recorría `mastery_by_concept`, así que un hueco
        solo contaba como bloqueante si el concepto bloqueado ya tenía
        evidencia — justo lo que no ocurre cuando el alumno aún no ha llegado
        ahí. El caso típico se perdía entero: quien falla el orden de las
        operaciones no ha intentado todavía despejar una ecuación.
        """
        graph = self._gate.graph
        canon = graph.canonicalize(concept)
        bloqueados = [
            sucesor
            for sucesor in graph.successors_of(canon)
            if canon in self._gate.evaluate(sucesor, profile).measured_gaps
        ]
        return tuple(bloqueados[:2])

    def _find_ready_successor(self, concept: str, profile: StudentProfile) -> str | None:
        graph = self._gate.graph
        canon = graph.canonicalize(concept)
        for candidate in graph.successors_of(canon):
            gate = self._gate.evaluate(candidate, profile)
            if (
                not gate.measured_gaps
                and profile.effective_concept_mastery(candidate) < 0.7
            ):
                return candidate
        return None
