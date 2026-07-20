import json

import httpx

from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.ports.ia_analyst import IAAnalyst
from src.domain.value_objects.analysis_result import AnalysisResult
from src.domain.value_objects.question import Quiz, QuizQuestion
from src.infrastructure.config import settings

_OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIAnalyst(IAAnalyst):

    def __init__(self) -> None:
        self._api_key = settings.OPENAI_API_KEY
        self._model = settings.OPENAI_MODEL
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def _chat(self, system_prompt: str, user_message: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.3,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=self._headers,
                json=payload,
                timeout=60,
            )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    async def analyze(self, document: DocumentAggregate) -> AnalysisResult:
        system_prompt = (
            "Eres un asistente educativo. Analiza el texto proporcionado y responde "
            "exclusivamente en JSON con las claves: summary (string), "
            "key_concepts (array de strings), suggested_questions (array de strings)."
        )
        user_message = f"Texto a analizar:\n\n{document.content}"

        raw = await self._chat(system_prompt, user_message)

        start = raw.find("{")
        end = raw.rfind("}") + 1
        data = json.loads(raw[start:end])

        return AnalysisResult(
            summary=data.get("summary", ""),
            key_concepts=data.get("key_concepts", []),
            suggested_questions=data.get("suggested_questions", []),
        )

    async def answer_question(self, context: str, question: str) -> str:
        system_prompt = (
            "Eres un tutor educativo. Responde la pregunta del estudiante basándote "
            "únicamente en el contexto proporcionado. Sé claro y conciso."
        )
        user_message = f"Contexto:\n{context}\n\nPregunta: {question}"
        return await self._chat(system_prompt, user_message)

    async def generate_quiz(self, document: DocumentAggregate, num_questions: int = 5) -> Quiz:
        system_prompt = (
            "Eres un experto en pedagogía. Genera exactamente "
            f"{num_questions} preguntas de opción múltiple en JSON: "
            '{"questions": [{"text": "...", "options": {"A": "...", "B": "...", "C": "...", "D": "..."}, "correct_answer": "A", "difficulty": "medium"}, ...]}. '
            "Sin texto adicional."
        )
        user_message = f"Texto:\n\n{document.content}"
        raw = await self._chat(system_prompt, user_message)

        start = raw.find("{")
        end = raw.rfind("}") + 1
        data = json.loads(raw[start:end])

        questions_data = data.get("questions", [])
        questions = []
        for q in questions_data:
            questions.append(QuizQuestion(
                text=q["text"],
                options=q["options"],
                correct_answer=q["correct_answer"],
                difficulty=q.get("difficulty", "medium"),
            ))
        return Quiz(questions=questions)