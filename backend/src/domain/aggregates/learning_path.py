from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import UUID, uuid4

from src.domain.concept_identity import canonicalize_concept
from src.domain.value_objects.question import Difficulty


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


#: `assumed`: prerrequisito sin evidencia que se da por sabido. "No medido" no es
#: "medido en cero" (invariante 3): no se enseña ni bloquea a sus dependientes,
#: salvo que la evidencia diga lo contrario (ADR-028).
ModuleStatus = Literal["locked", "available", "in_progress", "completed", "assumed"]

#: Mastery a partir del cual un módulo está dominado. Mismo número para la ruta y
#: para la clase: no puede haber dos definiciones de "ya lo sabe".
MASTERY_COMPLETED = 0.7


class ModuleKind(str, Enum):
    #: Lo que el estudiante vino a aprender: siempre se enseña.
    CONTENT = "content"
    #: Base del tema: solo se enseña si hay evidencia de que flojea.
    PREREQUISITE = "prerequisite"


class TeachingPhase(str, Enum):
    """Dónde está la clase. Se persiste con la ruta: sobrevive entre peticiones (ADR-028)."""

    ASSESSMENT = "assessment"  # falta la nivelación del tema
    TEACHING = "teaching"  # toca explicar el concepto actual
    CHECK = "check"  # explicación entregada; se espera la comprobación
    REMEDIATION = "remediation"  # desvío a un prerrequisito; luego se vuelve
    ADVANCE = "advance"  # dominó el concepto; toca el siguiente
    COMPLETED = "completed"  # no queda nada que enseñar en la ruta


class LessonVariant(str, Enum):
    """Qué tipo de explicación toca. La elige la política, no el modelo."""

    INTRODUCE = "introduce"
    NEW_EXAMPLE = "new_example"
    REFORMULATE = "reformulate"
    REMEDIATE = "remediate"
    CONSOLIDATE = "consolidate"
    RESUME = "resume"
    #: Repaso: lo superó, pero el olvido lo bajó del umbral (motor, ADR-032).
    REVIEW = "review"


class CheckOutcome(str, Enum):
    UNDERSTOOD = "understood"
    PARTIAL = "partial"
    NOT_UNDERSTOOD = "not_understood"


@dataclass
class TeachingState:
    """Cursor de la clase. Solo mecánica y memoria del turno: el mastery vive en el perfil."""

    phase: TeachingPhase = TeachingPhase.ASSESSMENT
    concept: str | None = None
    #: Concepto al que se vuelve al terminar un desvío de remediación.
    return_to: str | None = None
    variant: LessonVariant = LessonVariant.INTRODUCE
    #: Quiz de comprobación pendiente de responder (lo califica el flujo de quizzes).
    pending_check_quiz_id: UUID | None = None
    #: Última explicación entregada: una nueva petición la recupera tal cual.
    lesson_markdown: str = ""
    #: Resumen corto del último ejemplo, para no repetirlo.
    last_example: str = ""
    checks_on_concept: int = 0
    failures_on_concept: int = 0
    understood_streak: int = 0
    last_outcome: CheckOutcome | None = None
    #: Conceptos cuyo ciclo de comprobación ya superó. Su mastery sigue en el
    #: perfil (puede estar afianzándose): esto solo evita volver a enseñarlos.
    passed_concepts: list[str] = field(default_factory=list)
    #: Por qué la clase está donde está, en una frase para el estudiante.
    reason: str = ""
    updated_at: datetime = field(default_factory=_utc_now)


@dataclass
class LearningModule:
    """Unidad de la ruta de aprendizaje con estado y progreso propio."""

    id: UUID = field(default_factory=uuid4)
    title: str = ""
    concept: str = ""
    difficulty: Difficulty = Difficulty.EASY
    prerequisites: list[str] = field(default_factory=list)
    status: ModuleStatus = "locked"
    mastery: float = 0.0
    position: int = 0
    kind: ModuleKind = ModuleKind.CONTENT


@dataclass
class LearningPathAggregate:
    """Ruta de aprendizaje de un estudiante sobre una materia/tema.

    Es un grafo ordenado de módulos (conceptos) encadenados por prerrequisitos.
    LARIA desbloquea módulos según el mastery previo y puertas de prerrequisito.

    **La ruta es un plan, no una fuente de verdad del aprendizaje.** El mastery
    de cada módulo se *proyecta* desde `StudentProfile` en cada lectura
    (`project_mastery`); nadie lo declara ni se persiste como verdad. Antes
    existía un endpoint que dejaba al cliente escribir su propio mastery, lo
    que creaba una segunda verdad —nunca sincronizada con la evidencia— en un
    sistema cuyo principio es que responder bien no prueba comprensión
    (ADR-008).
    """

    id: UUID = field(default_factory=uuid4)
    owner_id: UUID = field(default_factory=uuid4)
    subject: str = ""
    title: str = ""
    modules: list[LearningModule] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    #: Tema canónico de la ruta (clave del nivel en el perfil). Vacío en rutas manuales.
    topic: str = ""
    teaching: TeachingState = field(default_factory=TeachingState)

    @staticmethod
    def create_for_topic(
        owner_id: UUID,
        topic: str,
        label: str,
        modules: list[dict],
    ) -> "LearningPathAggregate":
        """Ruta de un tema tras la nivelación. `modules` ya viene ordenado, bases primero.

        Cada módulo: concept, title, prerequisites (dentro de la ruta) y kind.
        Un prerrequisito que apunte fuera de la ruta se descarta: la ruta tiene
        que poder decidir sola sin un grafo externo.
        """
        path = LearningPathAggregate.create(owner_id, label or topic, title=label or topic)
        path.topic = canonicalize_concept(topic)
        vistos: set[str] = set()
        for i, m in enumerate(modules):
            concept = canonicalize_concept(m.get("concept", ""))
            if not concept or concept in vistos:
                continue
            prereqs = [p for p in (canonicalize_concept(x) for x in m.get("prerequisites", [])) if p in vistos]
            path.modules.append(
                LearningModule(
                    title=(m.get("title") or concept).strip()[:200],
                    concept=concept,
                    difficulty=Difficulty(m.get("difficulty", "medium")),
                    prerequisites=prereqs,
                    status="locked" if prereqs else "available",
                    position=len(path.modules),
                    kind=ModuleKind(m.get("kind", ModuleKind.CONTENT)),
                )
            )
            vistos.add(concept)
        if not path.modules:
            raise ValueError("La ruta necesita al menos un concepto.")
        return path

    def module(self, concept: str) -> LearningModule | None:
        return self._module_by_concept(concept)

    # --- Mecánica de la clase (las DECISIONES las toma TeachingPolicy) -----------

    def start_teaching(
        self,
        concept: str,
        variant: LessonVariant,
        phase: TeachingPhase = TeachingPhase.TEACHING,
        return_to: str | None = None,
        reason: str = "",
    ) -> None:
        """Fija el concepto, el tipo de explicación y la fase que decidió la política."""
        if phase not in (TeachingPhase.TEACHING, TeachingPhase.REMEDIATION, TeachingPhase.ADVANCE):
            raise ValueError(f"Fase no válida para empezar a enseñar: {phase}")
        concept = canonicalize_concept(concept)
        t = self.teaching
        if concept != t.concept:
            t.checks_on_concept = 0
            t.failures_on_concept = 0
            t.understood_streak = 0
            t.last_example = ""
        t.concept = concept
        t.variant = variant
        t.return_to = canonicalize_concept(return_to) if return_to else None
        t.phase = phase
        t.reason = reason
        t.pending_check_quiz_id = None
        self._touch()

    def deliver_lesson(self, markdown: str, example_summary: str, check_quiz_id: UUID) -> None:
        """La explicación ya se entregó: queda esperando la comprobación."""
        t = self.teaching
        if t.concept is None:
            raise ValueError("No hay concepto en curso.")
        t.lesson_markdown = markdown
        t.last_example = (example_summary or "")[:300]
        t.pending_check_quiz_id = check_quiz_id
        t.phase = TeachingPhase.CHECK
        self._touch()

    def record_check(self, outcome: CheckOutcome) -> None:
        """Registra el resultado de la comprobación pendiente (contadores del concepto)."""
        t = self.teaching
        if t.phase != TeachingPhase.CHECK or t.pending_check_quiz_id is None:
            raise ValueError("No hay una comprobación pendiente.")
        t.checks_on_concept += 1
        t.last_outcome = outcome
        t.pending_check_quiz_id = None
        if outcome == CheckOutcome.UNDERSTOOD:
            t.understood_streak += 1
        else:
            t.understood_streak = 0
        if outcome == CheckOutcome.NOT_UNDERSTOOD:
            t.failures_on_concept += 1
        self._touch()

    def reopen_for_review(self, concept: str, reason: str) -> None:
        """Una ruta completada vuelve a abrirse para repasar un concepto que se olvidó."""
        key = canonicalize_concept(concept)
        if key in self.teaching.passed_concepts:
            self.teaching.passed_concepts.remove(key)
        self.teaching.last_outcome = None
        self.start_teaching(key, LessonVariant.REVIEW, phase=TeachingPhase.TEACHING, reason=reason)

    def mark_passed(self, concept: str) -> None:
        key = canonicalize_concept(concept)
        if key and key not in self.teaching.passed_concepts:
            self.teaching.passed_concepts.append(key)
            self._touch()

    def complete(self, reason: str = "") -> None:
        t = self.teaching
        t.phase = TeachingPhase.COMPLETED
        t.reason = reason
        t.concept = None
        t.return_to = None
        t.pending_check_quiz_id = None
        self._touch()

    def await_assessment(self) -> None:
        self.teaching.phase = TeachingPhase.ASSESSMENT
        self._touch()

    def _touch(self) -> None:
        self.teaching.updated_at = _utc_now()
        self.updated_at = self.teaching.updated_at

    def prerequisite_edges(self) -> list[tuple[str, str]]:
        """(concepto, prerrequisito) dentro de la ruta: el grafo que usa el gate."""
        return [(m.concept, p) for m in self.modules for p in m.prerequisites]

    @staticmethod
    def create(
        owner_id: UUID,
        subject: str,
        title: str | None = None,
        modules: list[dict] | None = None,
    ) -> "LearningPathAggregate":
        subject = (subject or "").strip()
        if not subject:
            raise ValueError("La materia no puede estar vacía")
        path = LearningPathAggregate(
            owner_id=owner_id,
            subject=subject,
            title=(title or "Ruta de aprendizaje").strip(),
        )
        for i, m in enumerate(modules or []):
            concept = canonicalize_concept(m.get("concept", "") or "")
            if not concept:
                continue
            diff = m.get("difficulty", Difficulty.EASY)
            if isinstance(diff, str):
                diff = Difficulty(diff)
            path.modules.append(
                LearningModule(
                    title=m.get("title", "").strip() or concept,
                    concept=concept,
                    difficulty=diff,
                    prerequisites=[canonicalize_concept(p) for p in m.get("prerequisites", []) if p],
                    status="available" if i == 0 else "locked",
                    position=i,
                )
            )
        # Abrir el primer módulo que no tenga prerequisitos satisficible:
        # si todos están locked, desbloquear el primero con prerequisitos vacíos.
        if path.modules and all(m.status == "locked" for m in path.modules):
            first = next((m for m in path.modules if not m.prerequisites), path.modules[0])
            first.status = "available"
        return path

    def _module_by_concept(self, concept: str) -> LearningModule | None:
        key = canonicalize_concept(concept)
        return next((m for m in self.modules if m.concept == key), None)

    def project_mastery(
        self,
        mastery_by_concept: dict[str, float],
        measured: set[str] | None = None,
    ) -> None:
        """Deriva el progreso de toda la ruta desde el mastery del perfil.

        Un concepto sin evidencia queda en 0.0: la ruta no inventa progreso, y
        un módulo solo se completa cuando la evidencia lo respalda.

        `measured`: conceptos con evidencia suficiente para decidir. Si se pasa,
        un prerrequisito SIN medir queda "assumed" (se da por sabido) en vez de
        bloquear el tema: no medido no es medido en cero (invariante 3).
        """
        for module in self.modules:
            self.record_mastery(module.concept, mastery_by_concept.get(module.concept, 0.0))
        if measured is not None:
            for module in self.modules:
                if (
                    module.kind == ModuleKind.PREREQUISITE
                    and module.status != "completed"
                    and module.concept not in measured
                ):
                    module.status = "assumed"
            self._unlock_dependents()

    def record_mastery(self, concept: str, mastery: float) -> None:
        """Aplica a un módulo el mastery proyectado y desbloquea sus dependientes.

        Primitiva de proyección: la llama `project_mastery` con números que
        vienen del perfil. No es una operación de escritura del cliente.
        """
        mod = self._module_by_concept(concept)
        if mod is None:
            return
        mod.mastery = max(0.0, min(1.0, mastery))
        # El estado es función del mastery proyectado, también cuando baja: sin
        # la rama del 0.0 un módulo se quedaba "completed" después de que el
        # perfil perdiera la evidencia (olvido, borrado del documento).
        if mod.mastery >= MASTERY_COMPLETED:
            mod.status = "completed"
        elif mod.mastery > 0.0:
            mod.status = "in_progress"
        else:
            mod.status = "locked" if mod.prerequisites else "available"
        self._unlock_dependents()
        self.updated_at = _utc_now()

    def _unlock_dependents(self) -> None:
        for mod in self.modules:
            if mod.status == "completed":
                continue
            if not mod.prerequisites:
                continue
            # Un módulo se desbloquea si TODOS sus prerrequisitos están completados.
            prereqs_done = all(
                (
                    self._module_by_concept(p) is not None
                    and self._module_by_concept(p).status in ("completed", "assumed")
                )
                for p in mod.prerequisites
            )
            if prereqs_done and mod.status == "locked":
                mod.status = "available"

    @property
    def progress(self) -> float:
        if not self.modules:
            return 0.0
        return sum(1 for m in self.modules if m.status == "completed") / len(self.modules)

    def is_owned_by(self, user_id: UUID) -> bool:
        return self.owner_id == user_id
