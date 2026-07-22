"""Política pedagógica: compone prompts a partir de PedagogicalDecision.

El modelo de IA solo genera lenguaje; LARIA decide modo, dificultad y restricciones.
"""
from dataclasses import dataclass

from src.domain.services.pedagogical_engine import PedagogicalDecision, PedagogicalMode
from src.domain.value_objects.question import Difficulty


@dataclass(frozen=True)
class ChatPrompt:
    system: str
    user: str


_MODE_INSTRUCTIONS: dict[PedagogicalMode, str] = {
    PedagogicalMode.EXPLAIN: (
        "Explica con claridad. No asumas conocimiento previo. "
        "Usa un ejemplo breve y verifica comprensión con una pregunta corta."
    ),
    PedagogicalMode.SOCRATIC: (
        "Guía con preguntas socráticas. No entregues la respuesta completa de inmediato. "
        "Pide razonamiento del estudiante antes de concluir."
    ),
    PedagogicalMode.SCAFFOLD: (
        "Usa andamiaje: pista → ejemplo parcial → invitación a completar. "
        "Reduce carga cognitiva; un paso a la vez."
    ),
    PedagogicalMode.PRACTICE: (
        "Enfócate en práctica activa. Prioriza ítems alineados a la dificultad objetivo."
    ),
}


class TutorPolicy:
    """Selecciona prompts y objetivos de aprendizaje para cada caso de uso."""

    def analyze_document(self, content: str) -> ChatPrompt:
        return ChatPrompt(
            system=(
                "Eres un asistente educativo. Analiza el texto proporcionado y responde "
                "exclusivamente en JSON con las claves: summary (string), "
                "key_concepts (array de strings), suggested_questions (array de strings)."
            ),
            user=f"Texto a analizar:\n\n{content}",
        )

    def answer_question(
        self,
        context: str,
        question: str,
        decision: PedagogicalDecision | None = None,
    ) -> ChatPrompt:
        if decision is None:
            system = (
                "Eres un tutor educativo. Responde la pregunta del estudiante basándote "
                "únicamente en el contexto proporcionado. Sé claro y conciso. "
                "Si el estudiante muestra confusión, aclara con un ejemplo breve sin "
                "entregar la respuesta completa de un examen."
            )
        else:
            focus = ", ".join(decision.focus_concepts) or "los conceptos del documento"
            anti = (
                "Nunca reveles respuestas de examen ni soluciones completas de evaluación. "
                if decision.anti_spoiler
                else ""
            )
            system = (
                f"Eres un tutor adaptativo de LARIA. Modo: {decision.mode.value}. "
                f"Objetivo: {decision.objective} "
                f"Dificultad objetivo: {decision.target_difficulty.value}. "
                f"Foco conceptual: {focus}. "
                f"Evidencia del estudiante: {decision.evidence_summary}. "
                f"{_MODE_INSTRUCTIONS[decision.mode]} "
                f"{anti}"
                "Basa la respuesta únicamente en el contexto proporcionado. "
                "No asumas que una respuesta correcta previa implica comprensión profunda."
            )
        return ChatPrompt(
            system=system,
            user=f"Contexto:\n{context}\n\nPregunta: {question}",
        )

    def generate_quiz(
        self,
        content: str,
        num_questions: int,
        decision: PedagogicalDecision | None = None,
    ) -> ChatPrompt:
        difficulty = (
            decision.target_difficulty.value if decision else Difficulty.MEDIUM.value
        )
        focus = ""
        if decision and decision.focus_concepts:
            focus = (
                " Prioriza estos conceptos débiles del estudiante: "
                + ", ".join(decision.focus_concepts)
                + "."
            )
        mode_note = ""
        if decision:
            mode_note = (
                f" Estrategia LARIA: {decision.mode.value}; "
                f"objetivo: {decision.objective} "
                f"Evidencia: {decision.evidence_summary}."
            )
        return ChatPrompt(
            system=(
                "Eres un experto en pedagogía. Genera exactamente "
                f"{num_questions} preguntas de opción múltiple en JSON: "
                '{"questions": [{"text": "...", "options": {"A": "...", "B": "...", '
                '"C": "...", "D": "..."}, "correct_answer": "A", "difficulty": '
                f'"{difficulty}"}}, ...]}}. '
                f"La dificultad de la mayoría de ítems debe ser '{difficulty}'.{focus}"
                f"{mode_note} "
                "IMPORTANTE: reparte correct_answer entre A, B, C y D de forma equilibrada "
                "(no pongas casi todas en A). Sin texto adicional."
            ),
            user=f"Texto:\n\n{content}",
        )
