import json
import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.value_objects.analysis_result import AnalysisResult
from src.domain.value_objects.question import Quiz
from src.infrastructure.openai.openai_ia_analyst import OpenAIAnalyst


@pytest.fixture
def analyst() -> OpenAIAnalyst:
    return OpenAIAnalyst()


@pytest.mark.asyncio
async def test_analyze_parsea_json_correctamente(analyst: OpenAIAnalyst):
    doc = DocumentAggregate.upload(uuid4(), "test.txt", "Contenido educativo.", "Historia")
    fake_json = json.dumps({
        "summary": "Resumen del texto.",
        "key_concepts": ["concepto1", "concepto2"],
        "suggested_questions": ["¿Pregunta 1?", "¿Pregunta 2?"],
    })

    with patch.object(analyst, "_chat", AsyncMock(return_value=fake_json)):
        result = await analyst.analyze(doc)

    assert isinstance(result, AnalysisResult)
    assert result.summary == "Resumen del texto."
    assert result.key_concepts == ["concepto1", "concepto2"]
    assert result.suggested_questions == ["¿Pregunta 1?", "¿Pregunta 2?"]


@pytest.mark.asyncio
async def test_analyze_extrae_json_aunque_haya_texto_extra(analyst: OpenAIAnalyst):
    doc = DocumentAggregate.upload(uuid4(), "test.txt", "x", "Historia")
    raw = f"Texto previo\n{json.dumps({'summary': 'S', 'key_concepts': [], 'suggested_questions': []})}\nTexto posterior"

    with patch.object(analyst, "_chat", AsyncMock(return_value=raw)):
        result = await analyst.analyze(doc)

    assert result.summary == "S"


@pytest.mark.asyncio
async def test_answer_question_devuelve_texto(analyst: OpenAIAnalyst):
    with patch.object(analyst, "_chat", AsyncMock(return_value="Respuesta clara.")):
        result = await analyst.answer_question("Contexto del documento.", "¿Qué significa?")

    assert result == "Respuesta clara."


@pytest.mark.asyncio
async def test_generate_quiz_parsea_json(analyst: OpenAIAnalyst):
    doc = DocumentAggregate.upload(uuid4(), "test.txt", "Texto.", "Historia")
    fake_json = json.dumps({
        "questions": [
            {
                "text": "¿Pregunta 1?",
                "options": {"A": "Op1", "B": "Op2", "C": "Op3", "D": "Op4"},
                "correct_answer": "A",
                "difficulty": "easy",
            }
        ]
    })

    with patch.object(analyst, "_chat", AsyncMock(return_value=fake_json)):
        quiz = await analyst.generate_quiz(doc, num_questions=1)

    assert isinstance(quiz, Quiz)
    assert len(quiz.questions) == 1
    assert quiz.questions[0].text == "¿Pregunta 1?"
    assert quiz.questions[0].correct_answer == "A"


@pytest.mark.asyncio
async def test_generate_quiz_con_valores_por_defecto(analyst: OpenAIAnalyst):
    doc = DocumentAggregate.upload(uuid4(), "test.txt", "Texto.", "Historia")
    fake_json = json.dumps({
        "questions": [
            {
                "text": "Q1",
                "options": {"A": "1", "B": "2"},
                "correct_answer": "B",
            }
        ]
    })

    with patch.object(analyst, "_chat", AsyncMock(return_value=fake_json)):
        quiz = await analyst.generate_quiz(doc)

    assert quiz.questions[0].difficulty == "medium"