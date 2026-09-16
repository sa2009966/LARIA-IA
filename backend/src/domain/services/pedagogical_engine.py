from dataclasses import dataclass
from enum import Enum
from uuid import UUID
import logging

from src.domain.aggregates.concept_graph import ConceptGraph
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.aggregates.tutor_session import SessionStep, TutorSession
from src.domain.catalog.misconception_catalog import MisconceptionEntry
from src.domain.concept_identity import canonicalize_concept
from src.domain.services.cognitive_style import CognitiveStyle, CognitiveStyleSelector
from src.domain.services.difficulty_calculator import DifficultyCalculator
from src.domain.services.misconception_resolver import MisconceptionResolver
from src.domain.services.prerequisite_graph import GateAction, PrerequisiteGate
from src.domain.value_objects.question import Difficulty

logger = logging.getLogger("laria.pedagogy")


class PedagogicalMode(str, Enum):
    EXPLAIN = "explain"
    SOCRATIC = "socratic"
    SCAFFOLD = "scaffold"
    PRACTICE = "practice"


class TutorIntent(str, Enum):
    ASK = "ask"
    QUIZ = "quiz"


@dataclass(frozen=True)
class PedagogicalDecision:
    """Decisión de LARIA antes de generar lenguaje con el LLM."""

    mode: PedagogicalMode
    target_difficulty: Difficulty
    focus_concepts: tuple[str, ...]
    anti_spoiler: bool
    objective: str
    evidence_summary: str
    session_step: str = "introduce"
    cognitive_style: CognitiveStyle = CognitiveStyle.SIMPLE
    blocked_by_prereq: bool = False
    remediation_concepts: tuple[str, ...] = ()
    gate_action: GateAction = GateAction.PROCEED


class PedagogicalEngine:
    """Selecciona estrategia a partir de perfil (conceptos), prerrequisitos y sesión."""

    def __init__(
        self,
        gate: PrerequisiteGate | None = None,
        difficulty_calculator: DifficultyCalculator | None = None,
        style_selector: CognitiveStyleSelector | None = None,
        misconception_resolver: MisconceptionResolver | None = None,
    ) -> None:
        self._gate = gate or PrerequisiteGate()
        self._difficulty = difficulty_calculator or DifficultyCalculator()
        self._styles = style_selector or CognitiveStyleSelector()
        self._misconceptions = misconception_resolver or MisconceptionResolver()

    @staticmethod
    def _measured_mastery(
        profile: StudentProfile | None,
        focus: tuple[str, ...],
        doc_mastery: float,
    ) -> tuple[float, tuple[str, ...]]:
        """Mastery de los conceptos con evidencia, y cuáles son.

        Un concepto sin evidencia no aporta un 0.0 que arrastre la dificultad:
        "no medido" y "medido en cero" son estados distintos (ADR-006).
        """
        if profile is None or not focus:
            return doc_mastery, ()
        measured = tuple(c for c in focus if c in profile.mastery_by_concept)
        if not measured:
            return doc_mastery, ()
        return min(profile.effective_concept_mastery(c) for c in measured), measured

    @staticmethod
    def _return_promise(
        asked_focus: tuple[str, ...], remediation: tuple[str, ...]
    ) -> str:
        """Anuncia a qué se vuelve tras la base, sin prometer volver a la base."""
        pending = [c for c in asked_focus if c not in remediation][:2]
        if not pending:
            return "."
        return (
            f". Decir explícitamente que se volverá a {', '.join(pending)} "
            "en cuanto esas bases estén firmes."
        )

    def select(
        self,
        profile: StudentProfile | None,
        document_id: UUID,
        intent: TutorIntent,
        document_concepts: tuple[str, ...] = (),
        session: TutorSession | None = None,
        question: str = "",
        graph: ConceptGraph | None = None,
    ) -> PedagogicalDecision:
        # El motor lee el grafo; no lo muta (ADR-005, Decisión 5). Las
        # sugerencias derivadas del documento las escribe la capa de aplicación.
        active_graph = graph or self._gate.graph

        doc_mastery = profile.mastery_for(document_id) if profile else 0.0
        weak = ()
        if profile is not None:
            weak = tuple(profile.weakest_concepts(limit=5, document_id=document_id, use_effective=True))
        errors = tuple((profile.frequent_errors[:5] if profile else []))
        mapped_focus: list[str] = []
        unmapped_memory: list[str] = []
        mapped_entries: list[MisconceptionEntry] = []
        if profile is not None:
            for raw in profile.pedagogical_memory.frequent_misconceptions[:8]:
                entry = self._misconceptions.resolve_entry(raw)
                if entry is None:
                    key = canonicalize_concept(raw)
                    if key and key not in unmapped_memory:
                        unmapped_memory.append(key)
                    continue
                mapped_entries.append(entry)
                if entry.id not in mapped_focus:
                    mapped_focus.append(entry.id)
                anchor = canonicalize_concept(entry.anchor_concept)
                if anchor and anchor not in mapped_focus:
                    mapped_focus.append(anchor)
        doc_focus = tuple(
            canonicalize_concept(c) for c in document_concepts[:5] if c and canonicalize_concept(c)
        )
        focus = (
            tuple(mapped_focus[:5])
            or errors
            or weak
            or tuple(unmapped_memory[:5])
            or doc_focus
        )
        if session and session.focus_concepts:
            session_focus = tuple(session.focus_concepts[:5])
            merged = list(session_focus)
            for c in focus:
                if c not in merged:
                    merged.append(c)
            focus = tuple(merged[:5])

        # Gate de prerrequisitos sobre el foco principal (ADR-006): la fuerza
        # de la intervención escala con la evidencia. El foco solo se lidera
        # con la base en SEQUENCE; nunca se desvía en silencio.
        gate_action = GateAction.PROCEED
        remediation: tuple[str, ...] = ()
        asked_focus = focus
        if focus:
            gate = self._gate.evaluate(focus[0], profile, graph=active_graph)
            gate_action = gate.action
            remediation = gate.remediation_focus
            if gate.action == GateAction.SEQUENCE:
                focus = remediation + tuple(c for c in focus if c not in remediation)
                focus = focus[:5]
        blocked = gate_action == GateAction.SEQUENCE

        # Solo cuenta como mastery bajo lo que se midió: un concepto sin
        # evidencia no arrastra la dificultad hacia abajo (ADR-006).
        concept_m, measured_focus = self._measured_mastery(profile, focus, doc_mastery)
        # "Sin medir" es no tener evidencia que informe ESTA decisión: ni en los
        # conceptos del foco ni en el documento. La evidencia de documento
        # cuenta: un estudiante con intentos previos no es un recién llegado.
        doc_entry = profile.mastery_by_document.get(document_id) if profile else None
        doc_measured = doc_entry is not None and (
            doc_entry.attempts > 0 or doc_entry.struggle_signals > 0
        )
        unmeasured = not measured_focus and not doc_measured

        step = session.step if session else SessionStep.INTRODUCE
        struggle = profile.total_struggle_signals if profile else 0
        conf = 0.0
        if profile is not None and focus:
            confs = [
                profile.mastery_by_concept[c].confidence
                for c in focus
                if c in profile.mastery_by_concept
            ]
            conf = sum(confs) / len(confs) if confs else 0.0

        style = self._styles.select(profile, question=question)
        difficulty = self._difficulty.from_profile(profile, focus)

        evidence = (
            f"doc_mastery={doc_mastery:.2f}; concept_mastery={concept_m:.2f}; "
            f"confidence={conf:.2f}; pace={profile.pace if profile else 'unknown'}; "
            f"velocity={profile.learning_velocity if profile else 0:.2f}; "
            f"attempts={profile.total_attempts if profile else 0}; "
            f"struggle_signals={struggle}; step={step.value}; "
            f"hints={len(session.hints_given) if session else 0}; "
            f"style={style.value}; blocked_prereq={blocked}"
        )
        if mapped_entries:
            evidence += f"; mapped_misconception={mapped_entries[0].id}"

        in_hint = (
            session is not None
            and session.step == SessionStep.HINT
            and bool(session.hints_given)
        )
        in_practice = session is not None and session.step == SessionStep.PRACTICE

        if blocked:
            mode = PedagogicalMode.SCAFFOLD if intent == TutorIntent.ASK else PedagogicalMode.PRACTICE
            difficulty = Difficulty.EASY
            objective = (
                "Empezar por las bases que están costando: "
                + ", ".join(remediation or focus)
                + self._return_promise(asked_focus, remediation)
            )
        elif unmeasured and not in_hint:
            # Sin evidencia medida no se andamia: se explica y se apunta al
            # borde de la zona de desarrollo próximo. La respuesta del alumno
            # es la que revelará el nivel real (ADR-006).
            mode = PedagogicalMode.EXPLAIN if intent == TutorIntent.ASK else PedagogicalMode.PRACTICE
            objective = (
                "Responder lo que el estudiante preguntó, asumiendo capacidad. "
                "Cerrar con una pregunta breve de verificación para calibrar."
            )
            if gate_action == GateAction.INTEGRATE and remediation:
                objective += (
                    " Apoyar la explicación en "
                    + ", ".join(remediation)
                    + " sin convertirlo en el tema."
                )
        elif concept_m < 0.4 or in_hint:
            mode = PedagogicalMode.SCAFFOLD if intent == TutorIntent.ASK else PedagogicalMode.PRACTICE
            difficulty = Difficulty.EASY
            objective = "Construir comprensión básica con andamiaje y pistas."
            if in_hint:
                objective = (
                    "Continuar andamiaje sin repetir pistas previas; "
                    f"ya se dieron: {'; '.join(session.hints_given[-2:])}."
                )
                mode = PedagogicalMode.SCAFFOLD
        elif concept_m < 0.7 or in_practice:
            mode = PedagogicalMode.EXPLAIN if intent == TutorIntent.ASK else PedagogicalMode.PRACTICE
            if difficulty == Difficulty.HARD:
                difficulty = Difficulty.MEDIUM
            objective = "Consolidar conceptos débiles con explicación guiada y práctica."
        else:
            mode = PedagogicalMode.SOCRATIC if intent == TutorIntent.ASK else PedagogicalMode.PRACTICE
            objective = "Profundizar con razonamiento socrático y retos."

        # Oferta, no desvío: el alumno recibe lo que pidió y decide si repasa.
        if gate_action == GateAction.OFFER and remediation:
            objective += (
                " Responder primero la pregunta del estudiante y después ofrecerle, "
                "como opción y sin imponerla, repasar "
                + ", ".join(remediation)
                + "."
            )

        # Memoria: si hay analogías exitosas y estilo analogy, reforzar objetivo
        if profile and style == CognitiveStyle.ANALOGY and profile.pedagogical_memory.successful_analogies:
            objective += " Reutiliza analogías que ya funcionaron con este estudiante."
        if mapped_entries:
            top = mapped_entries[0]
            objective += (
                f" Prioriza la misconception {top.id} con estrategia {top.remediation_strategy}"
                f" (ancla: {canonicalize_concept(top.anchor_concept)})."
            )

        decision = PedagogicalDecision(
            mode=mode,
            target_difficulty=difficulty,
            focus_concepts=focus,
            # El anti-spoiler protege evaluaciones, no explicaciones: un tutor
            # que se niega a explicar cuando le preguntan no está tutorizando.
            anti_spoiler=intent == TutorIntent.QUIZ,
            objective=objective,
            evidence_summary=evidence,
            session_step=step.value,
            cognitive_style=style,
            blocked_by_prereq=blocked,
            remediation_concepts=remediation,
            gate_action=gate_action,
        )
        logger.info(
            "decision intent=%s mode=%s difficulty=%s style=%s blocked=%s focus=%s",
            intent.value,
            decision.mode.value,
            decision.target_difficulty.value,
            decision.cognitive_style.value,
            decision.blocked_by_prereq,
            list(decision.focus_concepts)[:5],
        )
        return decision
