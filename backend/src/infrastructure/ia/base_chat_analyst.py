"""Adaptador HTTP de chat completions; los prompts vienen de TutorPolicy (aplicación)."""
import json

import httpx

from src.domain.services.tutor_policy import TutorPolicy
from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.ports.ia_analyst import IAAnalysisError, IAAnalyst
from src.domain.value_objects.analysis_result import AnalysisResult
from src.domain.value_objects.question import Quiz, QuizQuestion

_MSG_PROVEEDOR = "El servicio de IA no está disponible en este momento."
_MSG_RESPUESTA = "El servicio de IA devolvió una respuesta inválida."


class BaseChatAnalyst(IAAnalyst):
    """Implementa analyze/answer_question/generate_quiz sobre un endpoint de chat.

    Las subclases solo definen `api_url`, `model` y `api_key`.
    La estrategia pedagógica vive en `TutorPolicy`.
    """

    api_url: str
    model: str

    def __init__(
        self,
        api_url: str,
        model: str,
        api_key: str,
        tutor_policy: TutorPolicy | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_url = api_url
        self.model = model
        self._policy = tutor_policy or TutorPolicy()
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._client = http_client
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
            self._owns_client = True
        return self._client

    async def _chat(self, system_prompt: str, user_message: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.3,
        }
        try:
            client = await self._get_client()
            response = await client.post(self.api_url, headers=self._headers, json=payload)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except IAAnalysisError:
            raise
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise IAAnalysisError(_MSG_PROVEEDOR) from exc
    @staticmethod
    def _extract_json(raw: str) -> dict:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise IAAnalysisError(_MSG_RESPUESTA)
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError as exc:
            raise IAAnalysisError(_MSG_RESPUESTA) from exc

    @staticmethod
    def _as_str_list(value) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]

    async def analyze(self, document: DocumentAggregate) -> AnalysisResult:
        prompt = self._policy.analyze_document(document.content)
        raw = await self._chat(prompt.system, prompt.user)
        data = self._extract_json(raw)

        return AnalysisResult(
            summary=data.get("summary", "") or "Sin resumen",
            key_concepts=self._as_str_list(data.get("key_concepts", [])),
            suggested_questions=self._as_str_list(data.get("suggested_questions", [])),
            confidence_score=float(data.get("confidence_score", 0.0) or 0.0),
        )

    async def answer_question(
        self, context: str, question: str, decision=None
    ) -> str:
        prompt = self._policy.answer_question(context, question, decision)
        return await self._chat(prompt.system, prompt.user)

    async def generate_quiz(
        self, document: DocumentAggregate, num_questions: int = 5, decision=None, context: str | None = None
    ) -> Quiz:
        text = context if context is not None else document.content
        prompt = self._policy.generate_quiz(text, num_questions, decision)
        raw = await self._chat(prompt.system, prompt.user)
        data = self._extract_json(raw)

        try:
            questions = []
            for q in data.get("questions", []):
                tags = q.get("concept_tags") or q.get("concepts") or []
                if isinstance(tags, str):
                    tags = [tags]
                questions.append(
                    QuizQuestion(
                        text=q["text"],
                        options=q["options"],
                        correct_answer=q["correct_answer"],
                        difficulty=q.get("difficulty", "medium"),
                        concept_tags=tuple(str(t) for t in tags),
                    )
                )
        except (KeyError, TypeError, ValueError) as exc:
            raise IAAnalysisError(_MSG_RESPUESTA) from exc
        return Quiz(questions=questions)
