"""El modelo devuelve JSON roto a veces: se pide en modo JSON y se reintenta una vez.

Contra Render, "¿Empezamos con unas preguntas rápidas sobre linux?" terminaba en
"El servicio de IA devolvió una respuesta inválida". Reproducido: ~1 de cada 4
respuestas cerraba con una llave de más ("…["configuración"]}}]}").
"""
import pytest

from src.domain.ports.ia_analyst import IAAnalysisError
from src.domain.services.diagnostic_planner import PlacementRound, plan_diagnostic
from src.domain.catalog.prerequisite_seeds import build_seeded_graph
from src.infrastructure.ia.base_chat_analyst import BaseChatAnalyst

BIEN = ('{"questions": [{"text": "¿ls?", "options": {"A": "ls", "B": "dir"}, '
        '"correct_answer": "A", "difficulty": "easy", "concept_tags": ["comando"]}]}')
ROTO = BIEN[:-2] + "}}]}"  # la llave de más que se vio en producción


class Analista(BaseChatAnalyst):
    def __init__(self, respuestas):
        self._respuestas = list(respuestas)
        self.llamadas = []
        self.model = "gpt-4o-mini"
        from src.domain.services.tutor_policy import TutorPolicy

        self._policy = TutorPolicy()

    async def _chat(self, system, user, **kw):
        self.llamadas.append(kw)
        return self._respuestas.pop(0)


def _plan():
    return plan_diagnostic("linux", build_seeded_graph("default"), PlacementRound.BASE)


@pytest.mark.asyncio
async def test_se_pide_en_modo_json():
    a = Analista([BIEN])

    quiz = await a.generate_diagnostic(_plan())

    assert len(quiz.questions) == 1
    assert a.llamadas[0]["json_mode"] is True


@pytest.mark.asyncio
async def test_un_json_roto_se_reintenta_una_vez():
    a = Analista([ROTO, BIEN])

    quiz = await a.generate_diagnostic(_plan())

    assert len(quiz.questions) == 1 and len(a.llamadas) == 2


@pytest.mark.asyncio
async def test_dos_seguidos_ya_es_error():
    a = Analista([ROTO, ROTO])

    with pytest.raises(IAAnalysisError):
        await a.generate_diagnostic(_plan())
    assert len(a.llamadas) == 2


@pytest.mark.asyncio
async def test_el_json_mode_viaja_en_la_peticion():
    """El flag tiene que llegar al proveedor como response_format."""
    enviados = []

    class Respuesta:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": BIEN}}], "usage": {}}

    class Cliente:
        async def post(self, url, headers=None, json=None):
            enviados.append(json)
            return Respuesta()

    a = BaseChatAnalyst.__new__(BaseChatAnalyst)
    a.model, a.api_url, a._headers, a._metrics = "gpt-4o-mini", "http://x", {}, None

    async def cliente():
        return Cliente()

    a._get_client = cliente
    await a._chat("s", "u", json_mode=True)
    await a._chat("s", "u")

    assert enviados[0]["response_format"] == {"type": "json_object"}
    assert "response_format" not in enviados[1], "el chat normal no va en modo JSON"
