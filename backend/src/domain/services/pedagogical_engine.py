from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from src.domain.aggregates.student_profile import StudentProfile
from src.domain.aggregates.tutor_session import SessionStep, TutorSession
from src.domain.value_objects.question import Difficulty


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


class PedagogicalEngine:
    """Selecciona estrategia a partir de perfil (conceptos), documento y sesión."""

    def select(
        self,
        profile: StudentProfile | None,
        document_id: UUID,
        intent: TutorIntent,
        document_concepts: tuple[str, ...] = (),
        session: TutorSession | None = None,
    ) -> PedagogicalDecision:
        doc_mastery = profile.mastery_for(document_id) if profile else 0.0
        weak = ()
        if profile is not None:
            weak = tuple(profile.weakest_concepts(limit=5, document_id=document_id))
        errors = tuple((profile.frequent_errors[:5] if profile else []))
        focus = weak or errors or tuple(c.strip().lower() for c in document_concepts[:5] if c)
        if session and session.focus_concepts:
            # Prioriza foco de sesión si existe
            session_focus = tuple(session.focus_concepts[:5])
            merged = list(session_focus)
            for c in focus:
                if c not in merged:
                    merged.append(c)
            focus = tuple(merged[:5])

        # Mastery dominante: peor concepto en foco, o mastery documento
        concept_m = doc_mastery
        if profile is not None and focus:
            concept_m = min(profile.concept_mastery_for(c) for c in focus)
            # Si el concepto no tiene intentos, concept_mastery_for=0 → novato en ese foco
            if all(profile.concept_mastery_for(c) == 0.0 and c not in profile.mastery_by_concept for c in focus):
                concept_m = doc_mastery

        step = session.step if session else SessionStep.INTRODUCE
        struggle = profile.total_struggle_signals if profile else 0
        evidence = (
            f"doc_mastery={doc_mastery:.2f}; concept_mastery={concept_m:.2f}; "
            f"pace={profile.pace if profile else 'unknown'}; "
            f"attempts={profile.total_attempts if profile else 0}; "
            f"struggle_signals={struggle}; step={step.value}; "
            f"hints={len(session.hints_given) if session else 0}"
        )

        # El step de sesión solo ajusta objetivo/modo si hay sesión real;
        # sin sesión, INTRODUCE no debe forzar scaffold a perfiles fuertes.
        in_hint = (
            session is not None
            and session.step == SessionStep.HINT
            and bool(session.hints_given)
        )
        in_practice = session is not None and session.step == SessionStep.PRACTICE

        if concept_m < 0.4 or in_hint:
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
            difficulty = Difficulty.MEDIUM
            objective = "Consolidar conceptos débiles con explicación guiada y práctica."
        else:
            mode = PedagogicalMode.SOCRATIC if intent == TutorIntent.ASK else PedagogicalMode.PRACTICE
            difficulty = Difficulty.HARD
            objective = "Profundizar con razonamiento socrático y retos."

        # Anti-spoiler más estricto en HINT
        anti = True
        return PedagogicalDecision(
            mode=mode,
            target_difficulty=difficulty,
            focus_concepts=focus,
            anti_spoiler=anti,
            objective=objective,
            evidence_summary=evidence,
            session_step=step.value,
        )
