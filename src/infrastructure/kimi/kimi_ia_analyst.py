import json
from datetime import datetime, timezone

import httpx

from src.domain.entities.analysis import Analysis
from src.domain.entities.document import Document
from src.domain.ports.ia_analyst import IAAnalyst
from src.infrastructure.config import settings

_KIMI_API_URL = "https://api.moonshot.cn/v1/chat/completions"
_DEFAULT_MODEL = "moonshot-v1-8k"


class KimiIAAnalyst(IAAnalyst):
    """Adaptador: implementa IAAnalyst usando la API de Kimi (Moonshot)."""

    def __init__(self) -> None:
        self._api_key = settings.KIMI_API_KEY
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _chat(self, system_prompt: str, user_message: str) -> str:
        payload = {
            "model": _DEFAULT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.3,
        }
        response = httpx.post(_KIMI_API_URL, headers=self._headers, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def analyze(self, document: Document) -> Analysis:
        system_prompt = (
            "Eres un asistente educativo. Analiza el texto proporcionado y responde "
            "exclusivamente en JSON con las claves: summary (string), "
            "key_concepts (array de strings), suggested_questions (array de strings)."
        )
        user_message = f"Texto a analizar:\n\n{document.content}"

        raw = self._chat(system_prompt, user_message)

        # Extrae el bloque JSON aunque haya texto adicional
        start = raw.find("{")
        end = raw.rfind("}") + 1
        data = json.loads(raw[start:end])

        return Analysis(
            id=None,
            document_id=document.id,  # type: ignore[arg-type]
            summary=data.get("summary", ""),
            key_concepts=data.get("key_concepts", []),
            suggested_questions=data.get("suggested_questions", []),
            model_used=_DEFAULT_MODEL,
            created_at=datetime.now(timezone.utc),
        )

    def answer_question(self, context: str, question: str) -> str:
        system_prompt = (
            "Eres un tutor educativo. Responde la pregunta del estudiante basándote "
            "únicamente en el contexto proporcionado. Sé claro y conciso."
        )
        user_message = f"Contexto:\n{context}\n\nPregunta: {question}"
        return self._chat(system_prompt, user_message)

    def generate_quiz(self, document: Document, num_questions: int = 5) -> list[str]:
        system_prompt = (
            "Eres un experto en pedagogía. Genera exactamente "
            f"{num_questions} preguntas de comprensión lectora en JSON: "
            '{"questions": ["pregunta1", ...]}. Sin texto adicional.'
        )
        user_message = f"Texto:\n\n{document.content}"
        raw = self._chat(system_prompt, user_message)

        start = raw.find("{")
        end = raw.rfind("}") + 1
        data = json.loads(raw[start:end])
        return data.get("questions", [])
