"""Tramos intermedio y avanzado con temario investigado (ADR-039), por HTTP.

El investigador es un doble (la búsqueda web es externa); lo que se comprueba es lo
que hace el backend con su resultado: módulos con ideas clave y fuentes, la lección
apoyada en ellas, la caché global y el respaldo si la búsqueda falla.
"""
import pytest
from fastapi.testclient import TestClient

from src.application.services.curriculum_research_service import CurriculumResearchService
from src.application.services.quiz_service import QuizService
from src.application.services.teaching_service import TeachingService
from src.application.services.topic_catalog import TopicCatalog
from src.domain.ports.lesson_generator import Source, SyllabusItem
from src.infrastructure.openai.web_researcher import ResearchFailed
from src.infrastructure.persistence.in_memory_curriculum_research_repo import (
    InMemoryCurriculumResearchRepository,
)
from src.interfaces.api import dependencies as deps
from src.main import app
from tests.api.test_clase_e2e import ModeloFalso, _auth, _leccion, _nivelarse, _ruta
from tests.api.test_tramos_e2e import _completar
from tests.conftest import clear_dependency_caches

KHAN = Source("Khan Academy", "https://es.khanacademy.org/math/x")


class Investigador:
    def __init__(self):
        self.pedidos, self.falla = [], False

    async def research(self, label, level, avoid=()):
        self.pedidos.append((label, level, avoid))
        if self.falla:
            raise ResearchFailed("caído")
        return [
            SyllabusItem("Variables"),  # ya visto: se descarta
            SyllabusItem(f"Comprensiones {level}", (), ("Crean listas en una línea", "Evitan bucles"), (KHAN,)),
            SyllabusItem(f"Generadores {level}", (f"Comprensiones {level}",), ("Producen valores bajo demanda",), (KHAN,)),
        ]


@pytest.fixture
def entorno_investigado():
    clear_dependency_caches()
    app.dependency_overrides.clear()
    modelo, investigador = ModeloFalso(), Investigador()
    cache = CurriculumResearchService(investigador, InMemoryCurriculumResearchRepository())

    def quiz_service():
        return QuizService(
            document_repository=deps.get_document_repo(), quiz_repository=deps.get_quiz_repo(),
            attempt_repository=deps.get_attempt_repo(), interaction_repository=deps.get_interaction_repo(),
            ia_analyst=modelo, event_bus=deps.get_event_bus(), profile_repository=deps.get_profile_repo(),
            session_repository=deps.get_session_repo(),
        )

    app.dependency_overrides[deps.get_quiz_service] = quiz_service
    app.dependency_overrides[deps.get_teaching_service] = lambda: TeachingService(
        path_repository=deps.get_learning_path_repo(), profile_repository=deps.get_profile_repo(),
        quiz_repository=deps.get_quiz_repo(), quiz_service=quiz_service(), lesson_generator=modelo,
        topic_catalog=TopicCatalog(), attempt_repository=deps.get_attempt_repo(), research=cache,
    )
    with TestClient(app) as c:
        yield c, modelo, investigador
    app.dependency_overrides.clear()
    clear_dependency_caches()


def test_el_tramo_intermedio_sale_de_la_investigacion_con_fuentes(entorno_investigado):
    c, modelo, investigador = entorno_investigado
    h = _auth(c)
    _nivelarse(c, h, "python", bien=False)
    ruta = _ruta(c, h, "python")
    assert investigador.pedidos == []  # el básico no se investiga
    _completar(c, h, ruta["id"])
    _nivelarse(c, h, "python")  # → intermedio

    paso = _leccion(c, h, ruta["id"])

    nuevos = [m for m in paso["path"]["modules"] if m["tier"] == "intermedio"]
    assert [m["title"] for m in nuevos] == ["Comprensiones intermedio", "Generadores intermedio"]
    assert nuevos[0]["key_points"] == ["Crean listas en una línea", "Evitan bucles"]
    assert nuevos[0]["sources"] == [{"title": "Khan Academy", "url": "https://es.khanacademy.org/math/x"}]
    assert investigador.pedidos == [("Python", "intermedio", ("Variables", "Bucles"))]
    # La clase se apoya en lo investigado; el modelo no tuvo que inventar el temario.
    assert modelo.lecciones[-1].key_points == ("Crean listas en una línea", "Evitan bucles")
    assert not getattr(modelo, "tramos", [])


def test_se_investiga_una_vez_para_todos_los_estudiantes(entorno_investigado):
    c, _, investigador = entorno_investigado
    for _ in range(2):
        h = _auth(c)
        _nivelarse(c, h, "python")  # llegan en intermedio: primer tramo investigado
        ruta = _ruta(c, h, "python")
        assert ruta["tiers"] == ["intermedio"] and any(m["sources"] for m in ruta["modules"])
    assert len(investigador.pedidos) == 1


def test_si_la_busqueda_falla_el_tramo_sale_del_modelo(entorno_investigado):
    c, modelo, investigador = entorno_investigado
    investigador.falla = True
    h = _auth(c)
    _nivelarse(c, h, "python", bien=False)
    ruta = _ruta(c, h, "python")
    _completar(c, h, ruta["id"])
    _nivelarse(c, h, "python")

    paso = _leccion(c, h, ruta["id"])

    nuevos = [m for m in paso["path"]["modules"] if m["tier"] == "intermedio"]
    assert [m["title"] for m in nuevos] == ["Patrones intermedio", "Diseño intermedio"]
    assert all(m["sources"] == [] for m in nuevos)
    assert modelo.tramos  # respaldo: el temario del modelo
