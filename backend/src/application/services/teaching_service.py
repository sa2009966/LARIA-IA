"""La clase: nivelación → ruta → explicación → comprobación → siguiente paso (ADR-028).

Orquesta; no decide. Las decisiones (qué concepto, qué explicación, avanzar,
remediar) son de `TeachingPolicy`; el contenido lo redacta el modelo vía
`LessonGenerator`; la comprobación se guarda y se califica con el flujo de
quizzes de siempre, así que su evidencia llega al perfil por el mismo evento y
el mismo projector que cualquier quiz (un único sistema de mastery).

El estado vive en la ruta (`LearningPathAggregate.teaching`), persistida en su
repositorio: cada petición HTTP continúa exactamente donde quedó la anterior.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from src.application.dto.quiz_dto import QuizAttemptResultDTO
from src.application.services.quiz_service import QuizService
from src.application.services.topic_catalog import TopicCatalog
from src.domain.aggregates.learning_path import (
    CheckOutcome,
    LearningPathAggregate,
    ModuleKind,
    TeachingPhase,
)
from src.domain.aggregates.quiz_aggregate import QuizAggregate
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.catalog.prerequisite_seeds import seed_display_labels
from src.domain.concept_identity import canonicalize_concept
from src.domain.ports.lesson_generator import LessonGenerator, LessonRequest, SyllabusItem
from src.domain.ports.repositories import (
    LearningPathRepository,
    QuizAttemptRepository,
    QuizRepository,
    StudentProfileRepository,
)
from src.domain.services.cognitive_style import chosen_style
from src.domain.services.diagnostic_planner import display_label
from src.domain.services.teaching_policy import (
    NextStep,
    TeachingPolicy,
    check_difficulties,
    outcome_from,
)

logger = logging.getLogger("laria.teaching")

#: Un temario propuesto por el modelo se acota: más subtemas no caben en una clase.
MAX_SYLLABUS = 6


class PathNotFound(LookupError):
    pass


class AssessmentRequired(RuntimeError):
    """El tema aún no tiene nivelación: no se enseña sin saber de dónde partir."""


class NoPendingCheck(RuntimeError):
    """La comprobación enviada no es la que la clase está esperando."""


@dataclass(frozen=True)
class LessonStep:
    path: LearningPathAggregate
    #: El quiz de comprobación del paso; None si la ruta está completada.
    check: QuizAggregate | None


@dataclass(frozen=True)
class CheckResult:
    path: LearningPathAggregate
    outcome: CheckOutcome
    attempt: QuizAttemptResultDTO
    next: NextStep


class TeachingService:
    def __init__(
        self,
        path_repository: LearningPathRepository,
        profile_repository: StudentProfileRepository,
        quiz_repository: QuizRepository,
        quiz_service: QuizService,
        lesson_generator: LessonGenerator,
        topic_catalog: TopicCatalog,
        policy: TeachingPolicy | None = None,
        attempt_repository: QuizAttemptRepository | None = None,
    ) -> None:
        self._paths = path_repository
        self._profiles = profile_repository
        self._quizzes = quiz_repository
        self._quiz_service = quiz_service
        self._generator = lesson_generator
        self._topics = topic_catalog
        self._policy = policy or TeachingPolicy()
        self._attempts = attempt_repository

    # --- Ruta -----------------------------------------------------------------------

    async def path_for_topic(self, user_id: UUID, topic: str) -> LearningPathAggregate:
        """La ruta del tema: la existente si ya hay una, o una nueva desde el grafo.

        Idempotente: pedirla dos veces no crea dos rutas ni reinicia la clase.
        """
        if not (topic or "").strip():
            raise ValueError("Indica el tema de la ruta.")
        tema = await self._topics.canonical(topic)
        for existente in await self._paths.find_by_owner(user_id):
            if existente.topic == tema:
                await self._sync_assessment(existente, await self._profiles.find_by_student(user_id))
                await self._paths.save(existente)
                return existente

        perfil = await self._profiles.find_by_student(user_id)
        etiqueta = (perfil.label_for_topic(tema) if perfil else None) or display_label(topic)
        nivel = perfil.level_for_topic(tema) if perfil else None
        modulos = await self._modules_for(tema, etiqueta, nivel)
        path = LearningPathAggregate.create_for_topic(user_id, tema, etiqueta, modulos)
        await self._sync_assessment(path, perfil)
        await self._paths.save(path)
        return path

    async def _modules_for(self, tema: str, etiqueta: str, nivel: str | None) -> list[dict]:
        """Del grafo curricular si cubre el tema; si no, temario del modelo, validado."""
        grafo = await self._topics.graph()
        bases = grafo.all_prerequisites(tema)  # bases primero (orden topológico)
        nombres = seed_display_labels()
        if bases:
            dentro = set(bases)
            modulos = [
                {
                    "concept": b,
                    "title": display_label(nombres.get(b, b)),
                    "prerequisites": [p for p in grafo.prerequisites_of(b) if p in dentro],
                    "kind": ModuleKind.PREREQUISITE.value,
                    "difficulty": "easy",
                }
                for b in bases
            ]
            modulos.append(
                {
                    "concept": tema,
                    "title": etiqueta,
                    "prerequisites": list(grafo.prerequisites_of(tema)),
                    "kind": ModuleKind.CONTENT.value,
                    "difficulty": "medium",
                }
            )
            return modulos
        try:
            temario = await self._generator.propose_syllabus(etiqueta, nivel)
        except Exception:  # noqa: BLE001 — sin temario se enseña el tema entero
            logger.warning("temario_fallo tema=%s", tema)
            temario = []
        return validate_syllabus(temario, tema, etiqueta)

    async def _sync_assessment(self, path: LearningPathAggregate, perfil: StudentProfile | None) -> None:
        """ASSESSMENT mientras el tema no tenga nivelación; después, el primer paso."""
        if path.teaching.phase != TeachingPhase.ASSESSMENT:
            return
        if not path.topic or not (perfil and perfil.level_for_topic(path.topic)):
            return
        self._apply(path, self._policy.next_concept(path, perfil))

    def _apply(self, path: LearningPathAggregate, paso: NextStep) -> None:
        if paso.phase == TeachingPhase.COMPLETED or paso.concept is None:
            path.complete(paso.reason)
            return
        path.start_teaching(
            paso.concept, paso.variant, phase=paso.phase, return_to=paso.return_to, reason=paso.reason
        )

    async def get_owned(self, user_id: UUID, path_id: UUID) -> LearningPathAggregate:
        path = await self._paths.find_by_id(path_id)
        if path is None or not path.is_owned_by(user_id):
            raise PathNotFound(path_id)
        return path

    # --- Clase ----------------------------------------------------------------------

    async def lesson(self, user_id: UUID, path_id: UUID) -> LessonStep:
        """El paso actual de la clase. Si ya se entregó y espera respuesta, el MISMO.

        Así una recarga, otra pestaña u otra petición recuperan exactamente la
        explicación y la comprobación pendientes, sin generar ni cobrar otra.
        """
        path = await self.get_owned(user_id, path_id)
        perfil = await self._profiles.find_by_student(user_id)
        await self._sync_assessment(path, perfil)
        t = path.teaching
        if t.phase == TeachingPhase.ASSESSMENT:
            await self._paths.save(path)
            raise AssessmentRequired(path.title)
        if t.phase == TeachingPhase.COMPLETED:
            # Una ruta completada se reabre si el olvido bajó algo de lo aprendido.
            repaso = self._policy.due_review(path, perfil)
            if repaso is None:
                await self._paths.save(path)
                return LessonStep(path, None)
            path.reopen_for_review(
                repaso, f"Hace un tiempo que no practicas «{path.module(repaso).title if path.module(repaso) else repaso}»: lo repasamos."
            )
            t = path.teaching
        if t.phase == TeachingPhase.CHECK and t.pending_check_quiz_id is not None:
            pendiente = await self._quizzes.find_by_id(t.pending_check_quiz_id)
            if pendiente is not None:
                return LessonStep(path, pendiente)

        modulo = path.module(t.concept)
        vuelta = path.module(t.return_to) if t.return_to else None
        peticion = LessonRequest(
            topic_label=path.title,
            concept=t.concept,
            concept_title=modulo.title if modulo else t.concept,
            variant=t.variant,
            check_difficulties=check_difficulties(t.variant),
            level=perfil.level_for_topic(path.topic) if (perfil and path.topic) else None,
            style=chosen_style(perfil),
            return_to_title=vuelta.title if vuelta else None,
            avoid_example=t.last_example,
        )
        leccion = await self._generator.generate_lesson(peticion)
        quiz = QuizAggregate.create(
            None,
            user_id,
            list(leccion.check),
            topic=t.concept,
            topic_label=peticion.concept_title,
        )
        await self._quizzes.save(quiz)
        path.deliver_lesson(leccion.markdown, leccion.example_summary, quiz.id)
        await self._paths.save(path)
        return LessonStep(path, quiz)

    async def answer_check(
        self, user_id: UUID, path_id: UUID, quiz_id: UUID, answers: dict[int, str]
    ) -> CheckResult:
        """Califica la comprobación, registra la evidencia y decide el siguiente paso."""
        path = await self.get_owned(user_id, path_id)
        t = path.teaching
        if t.phase != TeachingPhase.CHECK or t.pending_check_quiz_id != quiz_id:
            raise NoPendingCheck(quiz_id)
        if self._attempts is not None and await self._attempts.find_by_quiz(quiz_id):
            # Dos envíos casi simultáneos (doble clic, dos pestañas): el segundo
            # ya no cuenta como otra comprobación ni como más evidencia.
            raise NoPendingCheck(quiz_id)
        # Mismo camino que cualquier quiz: calificación en servidor, evento y
        # projector. La evidencia de la clase NO tiene un sistema propio.
        intento = await self._quiz_service.submit_attempt(quiz_id, user_id, answers)
        correctas = sum(1 for q in intento.questions if q.is_correct)
        resultado = outcome_from(correctas, len(intento.questions))
        path.record_check(resultado)
        # Se relee: el projector acaba de aplicar la evidencia de este intento.
        perfil = await self._profiles.find_by_student(user_id)
        paso = self._policy.after_check(path, resultado, perfil)
        self._apply(path, paso)
        await self._paths.save(path)
        return CheckResult(path, resultado, intento, paso)

    async def projected(self, path: LearningPathAggregate, user_id: UUID) -> LearningPathAggregate:
        """La ruta con el mastery del perfil proyectado (y lo no medido como "assumed")."""
        perfil = await self._profiles.find_by_student(user_id)
        if perfil is None:
            path.project_mastery({}, measured=set())
            return path
        medidos = {c for c in perfil.mastery_by_concept if perfil.has_decision_evidence(c)}
        path.project_mastery(perfil.effective_mastery_by_concept(), measured=medidos)
        return path


def validate_syllabus(items: list[SyllabusItem], tema: str, etiqueta: str) -> list[dict]:
    """Temario del modelo → módulos válidos. El backend no se fía de la forma.

    - Máximo `MAX_SYLLABUS` subtemas, sin repetidos.
    - Un prerrequisito solo puede ser un subtema ANTERIOR de la lista: así no
      hay ciclos posibles y el orden de enseñanza es el de la lista.
    - Si no queda nada usable, la ruta es el tema entero.
    """
    modulos: list[dict] = []
    vistos: dict[str, str] = {}
    for item in items[:MAX_SYLLABUS]:
        clave = canonicalize_concept(item.title)
        if not clave or clave in vistos:
            continue
        prereqs = [vistos[k] for k in (canonicalize_concept(p) for p in item.prerequisites) if k in vistos]
        modulos.append(
            {
                "concept": clave,
                "title": item.title.strip()[:120],
                "prerequisites": prereqs,
                "kind": ModuleKind.CONTENT.value,
                "difficulty": "medium",
            }
        )
        vistos[clave] = clave
    if not modulos:
        return [{"concept": tema, "title": etiqueta, "prerequisites": [], "kind": ModuleKind.CONTENT.value}]
    return modulos
