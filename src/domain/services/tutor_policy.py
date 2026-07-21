"""Política pedagógica: decide prompts y estrategia antes de llamar al modelo.

El modelo de IA solo genera lenguaje; esta capa concentra la intención educativa.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ChatPrompt:
    system: str
    user: str


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

    def answer_question(self, context: str, question: str) -> ChatPrompt:
        return ChatPrompt(
            system=(
                "Eres un tutor educativo. Responde la pregunta del estudiante basándote "
                "únicamente en el contexto proporcionado. Sé claro y conciso. "
                "Si el estudiante muestra confusión, aclara con un ejemplo breve sin "
                "entregar la respuesta completa de un examen."
            ),
            user=f"Contexto:\n{context}\n\nPregunta: {question}",
        )

    def generate_quiz(self, content: str, num_questions: int) -> ChatPrompt:
        return ChatPrompt(
            system=(
                "Eres un experto en pedagogía. Genera exactamente "
                f"{num_questions} preguntas de opción múltiple en JSON: "
                '{"questions": [{"text": "...", "options": {"A": "...", "B": "...", '
                '"C": "...", "D": "..."}, "correct_answer": "A", "difficulty": "medium"}, ...]}. '
                "Sin texto adicional."
            ),
            user=f"Texto:\n\n{content}",
        )
