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


class QuizAnalyst(FakeAnalyst):
    def __init__(self) -> None:
        super().__init__()
        self.quiz_calls = 0

    async def generate_quiz(self, document, num_questions=5, decision=None, context=None):
        self.quiz_calls += 1
        from src.domain.value_objects.question import Quiz, QuizQuestion

        return Quiz(
            questions=[
                QuizQuestion(
                    text="P1",
                    options={"A": "1", "B": "2"},
                    correct_answer="A",
                    concept_tags=("algebra",),
                )
            ]
        )

    async def generate_quiz_with_model(
        self, document, num_questions=5, decision=None, context=None, *, model: str
    ):
        return await self.generate_quiz(document, num_questions, decision, context)


class PlainAnalyst:
    """Sin hooks *_with_model para cubrir fallback de LlmGate."""

    def __init__(self) -> None:
        self.calls = 0

    async def analyze(self, document):
        self.calls += 1
        return AnalysisResult(summary="plain", key_concepts=[], suggested_questions=[], confidence_score=0.5)

    async def answer_question(self, context, question, decision=None):
        self.calls += 1
        return "plain-answer"

    async def generate_quiz(self, document, num_questions=5, decision=None, context=None):
        from src.domain.value_objects.question import Quiz, QuizQuestion

        self.calls += 1
        return Quiz(
            questions=[
                QuizQuestion(
                    text="Q",
                    options={"A": "1", "B": "2"},
                    correct_answer="A",
                )
            ]
        )


@pytest.mark.asyncio
async def test_analyze_uses_embedded_result_without_llm():
    analyst = FakeAnalyst()
    gate = LlmGate(analyst)
    owner = uuid4()
    doc = DocumentAggregate.upload(owner, "a.txt", "content", "Historia")
    doc.complete_analysis(
        AnalysisResult(summary="embedded", key_concepts=[], suggested_questions=[], confidence_score=0.9)
    )
    result = await gate.analyze(doc)
    assert result.summary == "embedded"
    assert analyst.analyze_calls == 0


@pytest.mark.asyncio
async def test_analyze_force_refresh_bypasses_cache():
    analyst = FakeAnalyst()
    cache = InMemoryCache()
    gate = LlmGate(analyst, cache=cache)
    owner = uuid4()
    doc = DocumentAggregate.upload(owner, "a.txt", "content", "Historia")
    await gate.analyze(doc, force_refresh=True)
    await gate.analyze(doc, force_refresh=True)
    assert analyst.analyze_calls == 2


@pytest.mark.asyncio
async def test_generate_quiz_cache_hit():
    analyst = QuizAnalyst()
    cache = InMemoryCache()
    gate = LlmGate(analyst, cache=cache)
    owner = uuid4()
    doc = DocumentAggregate.upload(owner, "a.txt", "content", "Matemática")
    q1 = await gate.generate_quiz(doc, num_questions=1)
    q2 = await gate.generate_quiz(doc, num_questions=1)
    assert q1.questions[0].text == q2.questions[0].text
    assert analyst.quiz_calls == 1


@pytest.mark.asyncio
async def test_generate_quiz_reuses_existing_from_repo():
    from src.domain.aggregates.quiz_aggregate import QuizAggregate
    from src.domain.services.pedagogical_engine import PedagogicalDecision, PedagogicalMode
    from src.domain.services.cognitive_style import CognitiveStyle
    from src.domain.value_objects.question import Difficulty, QuizQuestion
    from src.infrastructure.persistence.in_memory_quiz_repo import InMemoryQuizRepository

    analyst = QuizAnalyst()
    repo = InMemoryQuizRepository()
    gate = LlmGate(analyst, quiz_repository=repo, metrics=InMemoryMetrics())
    owner = uuid4()
    doc = DocumentAggregate.upload(owner, "a.txt", "content", "Matemática")
    existing = QuizAggregate.create(
        doc.id,
        owner,
        [
            QuizQuestion(
                text="reuse",
                options={"A": "1", "B": "2"},
                correct_answer="A",
                concept_tags=("algebra",),
            )
        ],
    )
    await repo.save(existing)
    decision = PedagogicalDecision(
        mode=PedagogicalMode.EXPLAIN,
        target_difficulty=Difficulty.MEDIUM,
        focus_concepts=("algebra",),
        anti_spoiler=True,
        objective="obj",
        evidence_summary="ev",
        cognitive_style=CognitiveStyle.SIMPLE,
    )
    quiz = await gate.generate_quiz(doc, num_questions=1, decision=decision)
    assert quiz.questions[0].text == "reuse"
    assert analyst.quiz_calls == 0


@pytest.mark.asyncio
async def test_analyze_cache_hit_returns_without_llm():
    analyst = FakeAnalyst()
    cache = InMemoryCache()
    gate = LlmGate(analyst, cache=cache, metrics=InMemoryMetrics())
    owner = uuid4()
    doc = DocumentAggregate.upload(owner, "a.txt", "cached content", "Historia")
    await gate.analyze(doc, force_refresh=True)
    assert analyst.analyze_calls == 1
    doc2 = DocumentAggregate.upload(owner, "b.txt", "cached content", "Historia")
    result = await gate.analyze(doc2, force_refresh=False)
    assert result.summary == "resumen"
    assert analyst.analyze_calls == 1


@pytest.mark.asyncio
async def test_generate_quiz_cache_hit_from_json():
    analyst = QuizAnalyst()
    cache = InMemoryCache()
    gate = LlmGate(analyst, cache=cache, metrics=InMemoryMetrics())
    owner = uuid4()
    doc = DocumentAggregate.upload(owner, "a.txt", "content", "Matemática")
    await gate.generate_quiz(doc, num_questions=1)
    assert analyst.quiz_calls == 1
    await gate.generate_quiz(doc, num_questions=1)
    assert analyst.quiz_calls == 1


@pytest.mark.asyncio
async def test_generate_quiz_skips_empty_cached_questions():
    import json

    analyst = QuizAnalyst()
    cache = InMemoryCache()
    gate = LlmGate(analyst, cache=cache)
    owner = uuid4()
    doc = DocumentAggregate.upload(owner, "a.txt", "content", "Matemática")
    focus_hash = gate._hash("", "medium", gate.POLICY_VERSION, "1")
    await cache.set(f"quiz:{doc.id}:{focus_hash}", json.dumps({"questions": []}))
    quiz = await gate.generate_quiz(doc, num_questions=1)
    assert analyst.quiz_calls == 1
    assert len(quiz.questions) == 1


@pytest.mark.asyncio
async def test_invalidate_document_deletes_cache_keys():
    cache = InMemoryCache()
    gate = LlmGate(QuizAnalyst(), cache=cache)
    owner = uuid4()
    doc = DocumentAggregate.upload(owner, "a.txt", "algebra content", "Matemática")
    await gate.analyze(doc, force_refresh=True)
    await gate.generate_quiz(doc, num_questions=1)
    await gate.invalidate_document(doc.id, doc.content or "")
    assert await cache.get(f"analysis:{gate._hash(doc.content or '')}") is None


@pytest.mark.asyncio
async def test_invalidate_noop_without_cache():
    gate = LlmGate(FakeAnalyst(), cache=None)
    await gate.invalidate_document(uuid4(), "x")


@pytest.mark.asyncio
async def test_fallback_without_with_model_hooks():
    analyst = PlainAnalyst()
    gate = LlmGate(analyst, cache=InMemoryCache())
    doc = DocumentAggregate.upload(uuid4(), "f.txt", "body", "Historia")
    result = await gate.analyze(doc, force_refresh=True)
    assert result.summary == "plain"
    answer = await gate.answer_question("ctx", "q?")
    assert answer == "plain-answer"
    quiz = await gate.generate_quiz(doc, num_questions=1)
    assert len(quiz.questions) == 1

