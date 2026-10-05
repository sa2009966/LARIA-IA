"""Temario investigado (ADR-039): las fuentes salen de la búsqueda, nunca del modelo."""
import json

import httpx
import pytest

from src.application.services.curriculum_research_service import CurriculumResearchService
from src.domain.ports.lesson_generator import Source, SyllabusItem
from src.domain.services.tutor_policy import TutorPolicy
from src.infrastructure.openai.web_researcher import (
    OpenAIWebResearcher,
    ResearchFailed,
    clean_url,
    items_from,
    verified_sources,
)
from src.infrastructure.persistence.in_memory_curriculum_research_repo import (
    InMemoryCurriculumResearchRepository,
)


def _busqueda(anotaciones, consultadas=(), texto="Investigación con citas."):
    """Forma de la respuesta de /v1/responses con web_search (capturada 2026-10-05)."""
    return {"output": [
        {"type": "web_search_call", "action": {"type": "search", "sources": [{"url": u} for u in consultadas]}},
        {"type": "message", "content": [{"type": "output_text", "text": texto, "annotations": [
            {"type": "url_citation", "url": u, "title": t} for t, u in anotaciones]}]},
    ]}


def _json(data):
    return {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(data), "annotations": []}]}]}


def test_las_fuentes_son_las_citadas_sin_utm_sin_repetir_y_sin_foros():
    data = _busqueda(
        [("Khan Academy", "https://es.khanacademy.org/math/x?utm_source=openai"),
         ("Khan Academy", "https://es.khanacademy.org/math/x?utm_source=openai"),
         ("Hilo", "https://www.reddit.com/r/Matematicas/1"),
         ("Apuntes", "https://es.scribd.com/document/1")],
        consultadas=["https://portalacademico.cch.unam.mx/a?utm_source=openai&p=2"],
    )
    assert verified_sources(data) == [
        ("Khan Academy", "https://es.khanacademy.org/math/x"),
        ("portalacademico.cch.unam.mx", "https://portalacademico.cch.unam.mx/a?p=2"),
    ]
    assert clean_url("https://a.org/p?utm_medium=x#frag") == "https://a.org/p"


def test_un_numero_de_fuente_fuera_de_la_lista_se_descarta():
    fuentes = [("Khan", "https://k.org"), ("UNAM", "https://unam.mx")]
    items = items_from({"modules": [
        {"title": " Completar\nel cuadrado ", "prerequisites": [], "key_points": ["b^2 -\n 4ac decide"],
         "sources": [2, 7, "1", 2]},
        {"title": ""},
    ]}, fuentes)
    assert items == [SyllabusItem("Completar el cuadrado", (), ("b^2 - 4ac decide",), (Source("UNAM", "https://unam.mx"),))]


def _investigador(respuestas, pedidos):
    def responder(request):
        pedidos.append(json.loads(request.content))
        r = respuestas.pop(0)
        return r if isinstance(r, httpx.Response) else httpx.Response(200, json=r)

    return OpenAIWebResearcher("sk-x", http_client=httpx.AsyncClient(transport=httpx.MockTransport(responder)))


@pytest.mark.asyncio
async def test_investiga_obligando_a_buscar_y_estructura_citando_por_numero():
    pedidos = []
    r = _investigador([
        _busqueda([("Khan", "https://k.org")]),
        _json({"modules": [{"title": "Discriminante", "key_points": ["Decide cuántas raíces"], "sources": [1]}]}),
    ], pedidos)
    items = await r.research("Ecuaciones", "intermedio", ("Fórmula general",))
    assert items[0].sources == (Source("Khan", "https://k.org"),)
    busqueda, estructura = pedidos
    assert busqueda["tools"] == [{"type": "web_search"}] and busqueda["tool_choice"] == "required"
    assert busqueda["model"] == "gpt-4o" and "Fórmula general" in busqueda["input"]
    assert estructura["text"]["format"]["type"] == "json_object" and "tools" not in estructura
    assert "[1] Khan — https://k.org" in estructura["input"] and "JSON" in estructura["input"]


@pytest.mark.asyncio
async def test_sin_fuentes_no_hay_temario_investigado_ni_segunda_llamada():
    pedidos = []
    r = _investigador([_busqueda([])], pedidos)
    with pytest.raises(ResearchFailed):
        await r.research("Ecuaciones", "intermedio")
    assert len(pedidos) == 1


@pytest.mark.asyncio
async def test_un_rechazo_del_proveedor_es_researchfailed():
    r = _investigador([httpx.Response(400, json={"error": {"message": "bad"}})], [])
    with pytest.raises(ResearchFailed, match="400"):
        await r.research("Ecuaciones", "avanzado")


class Investigador:
    def __init__(self, falla=False):
        self.llamadas, self.falla = 0, falla

    async def research(self, label, level, avoid=()):
        self.llamadas += 1
        if self.falla:
            raise ResearchFailed("caído")
        return [SyllabusItem(f"{label} {level}", key_points=("idea",), sources=(Source("K", "https://k.org"),))]


@pytest.mark.asyncio
async def test_se_investiga_una_vez_por_tema_y_nivel_y_solo_intermedio_o_avanzado():
    inv = Investigador()
    s = CurriculumResearchService(inv, InMemoryCurriculumResearchRepository())
    assert await s.syllabus("python", "Python", "basico") is None
    a = await s.syllabus("python", "Python", "intermedio")
    b = await s.syllabus("python", "Python", "intermedio", ("otra cosa",))
    assert a == b and inv.llamadas == 1
    await s.syllabus("python", "Python", "avanzado")
    assert inv.llamadas == 2


@pytest.mark.asyncio
async def test_un_fallo_no_se_cachea_y_sin_investigador_no_hay_temario():
    inv = Investigador(falla=True)
    s = CurriculumResearchService(inv, InMemoryCurriculumResearchRepository())
    assert await s.syllabus("python", "Python", "intermedio") is None
    assert await s.syllabus("python", "Python", "intermedio") is None
    assert inv.llamadas == 2
    assert await CurriculumResearchService(None, InMemoryCurriculumResearchRepository()).syllabus(
        "python", "Python", "avanzado") is None


def test_la_leccion_se_apoya_en_las_ideas_clave():
    from src.domain.aggregates.learning_path import LessonVariant
    from src.domain.ports.lesson_generator import LessonRequest
    from src.domain.value_objects.question import Difficulty

    req = LessonRequest("Ecuaciones", "discriminante", "Discriminante", LessonVariant.INTRODUCE,
                        (Difficulty.EASY,), key_points=("b^2 - 4ac decide cuántas raíces",))
    assert "b^2 - 4ac decide cuántas raíces" in TutorPolicy().teaching_lesson(req).system
    sin = LessonRequest("Ecuaciones", "d", "D", LessonVariant.INTRODUCE, (Difficulty.EASY,))
    assert "ideas clave" not in TutorPolicy().teaching_lesson(sin).system
