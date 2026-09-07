"""Cobertura de BaseChatAnalyst con httpx mock."""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx

from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.ports.ia_analyst import IAAnalysisError
from src.infrastructure.ia.base_chat_analyst import BaseChatAnalyst
from src.infrastructure.metrics.in_memory_metrics import InMemoryMetrics


class _StubAnalyst(BaseChatAnalyst):
    api_url = "https://example.test/v1/chat"
    model = "test-model"


def _ok_response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        },
        request=httpx.Request("POST", "https://example.test/v1/chat"),
    )


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock(spec=httpx.AsyncClient)
    return client


@pytest.mark.asyncio
async def test_chat_http_status_error_records_metric(mock_client: AsyncMock):
    metrics = InMemoryMetrics()
    analyst = _StubAnalyst(
        api_url="https://example.test/v1/chat",
        model="test-model",
        api_key="sk-test",
        http_client=mock_client,
        metrics=metrics,
    )
    mock_client.post.return_value = httpx.Response(
        500,
        request=httpx.Request("POST", "https://example.test/v1/chat"),
    )
    with pytest.raises(IAAnalysisError, match="no está disponible"):
        await analyst._chat("sys", "user")
    snap = metrics.snapshot()
    assert any("laria_llm_calls" in k and "error" in k for k in snap["counters"])


@pytest.mark.asyncio
async def test_chat_success_records_metrics(mock_client: AsyncMock):
    metrics = InMemoryMetrics()
    analyst = _StubAnalyst(
        api_url="https://example.test/v1/chat",
        model="test-model",
        api_key="sk-test",
        http_client=mock_client,
        metrics=metrics,
    )
    mock_client.post.return_value = _ok_response('{"summary":"S","key_concepts":[],"suggested_questions":[]}')

    doc = DocumentAggregate.upload(uuid4(), "f.txt", "body", "Historia")
    result = await analyst.analyze(doc)
    assert result.summary == "S"
    snap = metrics.snapshot()
    assert any("laria_llm_latency_ms" in k for k in snap["histograms"])


@pytest.mark.asyncio
async def test_chat_http_error_raises_ia_analysis_error(mock_client: AsyncMock):
    analyst = _StubAnalyst(
        api_url="https://example.test/v1/chat",
        model="test-model",
        api_key="sk-test",
        http_client=mock_client,
        metrics=InMemoryMetrics(),
    )
    mock_client.post.side_effect = httpx.ConnectError("down")

    with pytest.raises(IAAnalysisError, match="no está disponible"):
        await analyst._chat("sys", "user")


@pytest.mark.asyncio
async def test_extract_json_invalid_raises():
    with pytest.raises(IAAnalysisError, match="inválida"):
        BaseChatAnalyst._extract_json("no json here")


@pytest.mark.asyncio
async def test_generate_quiz_invalid_structure_raises(mock_client: AsyncMock):
    analyst = _StubAnalyst(
        api_url="https://example.test/v1/chat",
        model="test-model",
        api_key="sk-test",
        http_client=mock_client,
    )
    mock_client.post.return_value = _ok_response(json.dumps({"questions": [{"text": "Q"}]}))
    doc = DocumentAggregate.upload(uuid4(), "f.txt", "body", "Historia")
    with pytest.raises(IAAnalysisError, match="inválida"):
        await analyst.generate_quiz(doc, num_questions=1)


@pytest.mark.asyncio
async def test_generate_quiz_string_concept_tags(mock_client: AsyncMock):
    analyst = _StubAnalyst(
        api_url="https://example.test/v1/chat",
        model="test-model",
        api_key="sk-test",
        http_client=mock_client,
    )
    payload = {
        "questions": [
            {
                "text": "Q1",
                "options": {"A": "1", "B": "2"},
                "correct_answer": "A",
                "concept_tags": "algebra",
            }
        ]
    }
    mock_client.post.return_value = _ok_response(json.dumps(payload))
    doc = DocumentAggregate.upload(uuid4(), "f.txt", "body", "Matemática")
    quiz = await analyst.generate_quiz(doc, num_questions=1)
    assert quiz.questions[0].concept_tags == ("algebra",)


@pytest.mark.asyncio
async def test_aclose_owned_client(mock_client: AsyncMock):
    analyst = _StubAnalyst(
        api_url="https://example.test/v1/chat",
        model="test-model",
        api_key="sk-test",
    )
    lazy = AsyncMock(spec=httpx.AsyncClient)
    analyst._client = lazy
    analyst._owns_client = True
    await analyst.aclose()
    lazy.aclose.assert_awaited_once()
    assert analyst._client is None


@pytest.mark.asyncio
async def test_lazy_client_created_when_missing():
    analyst = _StubAnalyst(
        api_url="https://example.test/v1/chat",
        model="test-model",
        api_key="sk-test",
    )
    with pytest.MonkeyPatch.context() as mp:
        created = AsyncMock(spec=httpx.AsyncClient)
        mp.setattr(httpx, "AsyncClient", MagicMock(return_value=created))
        client = await analyst._get_client()
        assert client is created
        assert analyst._owns_client is True


@pytest.mark.asyncio
async def test_as_str_list_non_list_returns_empty():
    assert BaseChatAnalyst._as_str_list("not-a-list") == []


@pytest.mark.asyncio
async def test_answer_question_with_model(mock_client: AsyncMock):
    analyst = _StubAnalyst(
        api_url="https://example.test/v1/chat",
        model="test-model",
        api_key="sk-test",
        http_client=mock_client,
    )
    mock_client.post.return_value = _ok_response("respuesta directa")
    out = await analyst.answer_question_with_model("ctx", "pregunta", None, model="gpt-strong")
    assert out == "respuesta directa"


@pytest.mark.asyncio
async def test_chat_passes_max_tokens(mock_client: AsyncMock):
    analyst = _StubAnalyst(
        api_url="https://example.test/v1/chat",
        model="test-model",
        api_key="sk-test",
        http_client=mock_client,
    )
    mock_client.post.return_value = _ok_response("ok")
    await analyst._chat("sys", "user", max_tokens=32)
    payload = mock_client.post.await_args.kwargs["json"]
    assert payload["max_tokens"] == 32


def test_extract_json_malformed_braces_raises():
    with pytest.raises(IAAnalysisError, match="inválida"):
        BaseChatAnalyst._extract_json("{not-json}")
