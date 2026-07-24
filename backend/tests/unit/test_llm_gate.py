"""Tests de caché y LlmGate (economía de tokens)."""
import pytest
from uuid import uuid4

from src.application.services.llm_gate import LlmGate
from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.value_objects.analysis_result import AnalysisResult
from src.infrastructure.cache.cache_adapters import InMemoryCache
from src.infrastructure.metrics.in_memory_metrics import InMemoryMetrics


class FakeAnalyst:
    def __init__(self) -> None:
        self.analyze_calls = 0
        self.ask_calls = 0

    async def analyze(self, document):
        self.analyze_calls += 1
        return AnalysisResult(
            summary="resumen",
            key_concepts=["variable"],
            suggested_questions=["¿qué es x?"],
            confidence_score=0.8,
        )

    async def analyze_with_model(self, document, model: str):
        return await self.analyze(document)

    async def answer_question(self, context, question, decision=None):
        self.ask_calls += 1
        return "respuesta tutor"

    async def answer_question_with_model(self, context, question, decision=None, *, model: str):
        return await self.answer_question(context, question, decision)

    async def generate_quiz(self, document, num_questions=5, decision=None, context=None):
        raise NotImplementedError

    async def generate_quiz_with_model(
        self, document, num_questions=5, decision=None, context=None, *, model: str
    ):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_analysis_cache_hit_skips_second_llm():
    analyst = FakeAnalyst()
    cache = InMemoryCache()
    metrics = InMemoryMetrics()
    gate = LlmGate(analyst, cache=cache, metrics=metrics)
    owner = uuid4()
    doc = DocumentAggregate.upload(owner, "a.txt", "contenido de álgebra", "Matemática")

    r1 = await gate.analyze(doc, force_refresh=False)
    assert r1.summary == "resumen"
    assert analyst.analyze_calls == 1

    doc2 = DocumentAggregate.upload(owner, "b.txt", "contenido de álgebra", "Matemática")
    r2 = await gate.analyze(doc2, force_refresh=False)
    assert r2.summary == "resumen"
    assert analyst.analyze_calls == 1


@pytest.mark.asyncio
async def test_ask_cache_reuses_equivalent_prompt():
    analyst = FakeAnalyst()
    cache = InMemoryCache()
    gate = LlmGate(analyst, cache=cache)
    a1 = await gate.answer_question("ctx", "¿qué es una variable?")
    a2 = await gate.answer_question("ctx", "¿qué es una variable?")
    assert a1 == a2
    assert analyst.ask_calls == 1
