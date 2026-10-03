"""Metas y tiempo de estudio (ADR-033): lo cuenta el servidor y no se infla."""
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.application.services.study_time_service import StudyTimeService
from src.domain.aggregates.study_time import credit_for, streak_days
from src.domain.ports.lesson_generator import LessonRequest
from src.domain.aggregates.learning_path import LessonVariant
from src.domain.services.tutor_policy import TutorPolicy
from src.domain.value_objects.question import Difficulty
from src.infrastructure.persistence.in_memory_study_time_repo import InMemoryStudyTimeRepository
from src.infrastructure.persistence.in_memory_student_profile_repo import InMemoryStudentProfileRepository
from src.infrastructure.persistence.in_memory_event_bus import InMemoryEventBus
from src.main import app

T0 = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)


def test_un_aviso_suma_como_mucho_60_s_y_no_mas_que_el_tiempo_real():
    assert credit_for(90, T0, None) == 60
    assert credit_for(60, T0, T0 - timedelta(seconds=20)) == 25, "20 s reales + 5 de margen"
    assert credit_for(60, T0, T0 - timedelta(minutes=5)) == 60


def test_la_racha_cuenta_dias_seguidos_cumpliendo_el_objetivo():
    hoy = date(2026, 10, 2)
    dias = {hoy - timedelta(days=i): m for i, m in enumerate([5, 30, 31, 40, 2])}

    assert streak_days(dias, hoy, 30) == 3, "hoy aún no cumple: cuenta la racha hasta ayer"
    assert streak_days(dias, hoy, None) == 5, "sin objetivo, basta con estudiar algo"


@pytest.mark.asyncio
async def test_dos_pestanas_no_cuentan_doble():
    s = StudyTimeService(InMemoryStudyTimeRepository(), InMemoryEventBus(), InMemoryStudentProfileRepository())
    uid = uuid4()
    for minuto in range(10):  # dos pestañas, cada una avisa cada minuto, desfasadas 30 s
        await s.record(uid, 60, "UTC", now=T0 + timedelta(minutes=minuto))
        r = await s.record(uid, 60, "UTC", now=T0 + timedelta(minutes=minuto, seconds=30))

    assert 9 <= r.today_minutes <= 12, r.today_minutes


@pytest.mark.asyncio
async def test_el_dia_es_el_de_la_zona_horaria_del_estudiante():
    s = StudyTimeService(InMemoryStudyTimeRepository(), InMemoryEventBus(), InMemoryStudentProfileRepository())
    uid = uuid4()
    tarde_utc = datetime(2026, 10, 2, 23, 30, tzinfo=timezone.utc)  # ya es día 3 en Madrid

    r = await s.record(uid, 60, "Europe/Madrid", now=tarde_utc)

    assert r.last_7_days[-1][0] == date(2026, 10, 3)


def test_la_sesion_corta_pide_explicaciones_breves():
    def sistema(minutos):
        req = LessonRequest(topic_label="T", concept="t", concept_title="T", variant=LessonVariant.INTRODUCE,
                            check_difficulties=(Difficulty.EASY,), session_minutes=minutos)
        return TutorPolicy().teaching_lesson(req).system

    assert "50-90 palabras" in sistema(10)
    assert "150-250 palabras" in sistema(45)
    assert "80-180 palabras" in sistema(None)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _h(c):
    s = uuid4().hex[:8]
    e = f"t_{s}@example.com"
    c.post("/api/v1/auth/register", json={"username": f"t_{s}", "email": e, "password": "Clave123"})
    return {"Authorization": "Bearer " + c.post("/api/v1/auth/token", data={"username": e, "password": "Clave123"}).json()["access_token"]}


def test_metas_y_tiempo_por_http(client):
    h = _h(client)

    assert client.put("/api/v1/learning/me/study-goals", headers=h,
                      json={"session_minutes": 20, "daily_goal_minutes": 30}).status_code == 200
    assert client.get("/api/v1/learning/me/study-goals", headers=h).json() == {"session_minutes": 20, "daily_goal_minutes": 30}
    r = client.post("/api/v1/learning/me/study-time", headers=h, json={"seconds": 60, "timezone": "America/Mexico_City"}).json()

    assert r["today_minutes"] == 1 and r["daily_goal_minutes"] == 30 and r["session_minutes"] == 20
    assert len(r["last_7_days"]) == 7 and r["goal_met_today"] is False


@pytest.mark.parametrize("cuerpo", [{"session_minutes": 25}, {"daily_goal_minutes": 7}])
def test_valores_no_permitidos_son_422(client, cuerpo):
    assert client.put("/api/v1/learning/me/study-goals", headers=_h(client), json=cuerpo).status_code == 422


def test_el_tiempo_estudiado_se_borra_con_la_cuenta(client):
    import asyncio
    from uuid import UUID

    from src.interfaces.api import dependencies as deps

    h = _h(client)
    client.post("/api/v1/learning/me/study-time", headers=h, json={"seconds": 60})
    uid = UUID(client.get("/api/v1/users/me", headers=h).json()["id"])

    assert client.request("DELETE", "/api/v1/users/me", headers=h, json={"password": "Clave123"}).status_code == 204
    assert asyncio.run(deps.get_study_time_repo().days_since(uid, date(2000, 1, 1))) == []
