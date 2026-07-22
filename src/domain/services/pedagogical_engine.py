from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from src.domain.aggregates.student_profile import StudentProfile
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


class PedagogicalEngine:
    """Selecciona estrategia pedagógica a partir del perfil y la intención."""

    def select(
        self,
        profile: StudentProfile | None,
        document_id: UUID,
        intent: TutorIntent,
        document_concepts: tuple[str, ...] = (),
    ) -> PedagogicalDecision:
        mastery = profile.mastery_for(document_id) if profile else 0.0
        errors = tuple((profile.frequent_errors[:5] if profile else []))
        focus = errors or document_concepts[:5]
        evidence = (
            f"mastery={mastery:.2f}; pace={profile.pace if profile else 'unknown'}; "
            f"attempts={profile.total_attempts if profile else 0}; "
            f"struggle_signals={profile.total_struggle_signals if profile else 0}"
        )

        if mastery < 0.4:
            mode = PedagogicalMode.SCAFFOLD if intent == TutorIntent.ASK else PedagogicalMode.PRACTICE
            difficulty = Difficulty.EASY
            objective = "Construir comprensión básica con andamiaje y pistas."
        elif mastery < 0.7:
            mode = PedagogicalMode.EXPLAIN if intent == TutorIntent.ASK else PedagogicalMode.PRACTICE
            difficulty = Difficulty.MEDIUM
            objective = "Consolidar conceptos con explicación guiada y práctica."
        else:
            mode = PedagogicalMode.SOCRATIC if intent == TutorIntent.ASK else PedagogicalMode.PRACTICE
            difficulty = Difficulty.HARD
            objective = "Profundizar con razonamiento socrático y retos."

        return PedagogicalDecision(
            mode=mode,
            target_difficulty=difficulty,
            focus_concepts=focus,
            anti_spoiler=True,
            objective=objective,
            evidence_summary=evidence,
        )
