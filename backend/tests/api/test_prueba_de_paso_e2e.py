"""La prueba de paso es de la ruta, no una nivelación nueva (ADR-042).

Informe de error: al terminar el tramo básico, "Hacer la prueba de paso" llevaba a la
nivelación inicial, que pedía otra vez el tema; escribiendo "Programación" nacía otra
ruta, y las preguntas eran del tema en general, no de lo estudiado. Aquí la prueba
sale de la ruta: mide sus módulos, no crea rutas y, si se supera, la misma ruta
abre el tramo siguiente.
"""
from src.domain.services.tutor_policy import TutorPolicy
from src.domain.services.diagnostic_planner import PlacementRound, plan_diagnostic, plan_passage_test
from tests.api.test_clase_e2e import (
    _auth,
    _correctas,
    _fallar,
    _leccion,
    _nivelarse,
    _ruta,
    entorno,  # noqa: F401  (fixture)
)
from tests.api.test_tramos_e2e import _completar


def _prueba(c, h, path_id):
    return c.post(f"/api/v1/learning/paths/{path_id}/passage-test", headers=h)


def test_la_prueba_de_paso_mide_lo_estudiado_y_abre_el_tramo_en_la_misma_ruta(entorno):  # noqa: F811
    c, modelo = entorno
    h = _auth(c)
    _nivelarse(c, h, "python", bien=False)  # básico
    ruta = _ruta(c, h, "python")
    _completar(c, h, ruta["id"])

    planes = []
    original = modelo.generate_diagnostic

    async def anota(plan, **kw):
        planes.append(plan)
        return await original(plan)

    modelo.generate_diagnostic = anota
    r = _prueba(c, h, ruta["id"])
    assert r.status_code == 201, r.text
    prueba = r.json()

    # Mide los módulos del tramo, no "el tema en general", con la ronda de su nivel.
    plan = planes[-1]
    assert set(plan.concepts) == {"variables", "bucles"} and plan.round.value == "base"
    assert plan.studied == ("Variables", "Bucles")
    assert prueba["topic"] == "python"
    intento = c.post(f"/api/v1/quizzes/{prueba['id']}/attempts", headers=h,
                     json={"answers": _correctas(prueba)}).json()
    assert intento["placement"]["level"] == "intermedio"

    paso = _leccion(c, h, ruta["id"])
    assert paso["path"]["id"] == ruta["id"]
    assert paso["path"]["tiers"] == ["basico", "intermedio"] and paso["check"] is not None
    rutas = c.get("/api/v1/learning/paths", headers=h).json()["paths"]
    assert [p["id"] for p in rutas] == [ruta["id"]], "no debe nacer otra ruta"


def test_si_no_la_supera_el_tramo_sigue_terminado_y_puede_repetirla(entorno):  # noqa: F811
    c, _ = entorno
    h = _auth(c)
    _nivelarse(c, h, "python", bien=False)
    ruta = _ruta(c, h, "python")
    _completar(c, h, ruta["id"])

    prueba = _prueba(c, h, ruta["id"]).json()
    intento = c.post(f"/api/v1/quizzes/{prueba['id']}/attempts", headers=h,
                     json={"answers": _fallar(prueba)}).json()
    assert intento["placement"]["level"] == "basico"
    # Fallarla es evidencia: lo que bajó del umbral se repasa en la misma ruta
    # (ADR-032), sin abrir el tramo siguiente.
    paso = _leccion(c, h, ruta["id"])
    assert paso["path"]["tiers"] == ["basico"] and paso["path"]["next_tier"] == "intermedio"
    assert paso["path"]["teaching"]["variant"] == "review"


def test_sin_tramo_terminado_no_hay_prueba_de_paso(entorno):  # noqa: F811
    c, _ = entorno
    h = _auth(c)
    _nivelarse(c, h, "python", bien=False)
    ruta = _ruta(c, h, "python")
    r = _prueba(c, h, ruta["id"])
    assert r.status_code == 409
    assert _prueba(c, h, "00000000-0000-0000-0000-000000000000").status_code == 404


def test_en_avanzado_completada_no_hay_prueba(entorno):  # noqa: F811
    c, _ = entorno
    h = _auth(c)
    _nivelarse(c, h, "python", bien=False)
    ruta = _ruta(c, h, "python")
    _completar(c, h, ruta["id"])
    for _ in range(2):  # básico → intermedio → avanzado, por su prueba de paso
        prueba = _prueba(c, h, ruta["id"]).json()
        c.post(f"/api/v1/quizzes/{prueba['id']}/attempts", headers=h, json={"answers": _correctas(prueba)})
        _completar(c, h, ruta["id"])
    final = c.get(f"/api/v1/learning/paths/{ruta['id']}", headers=h).json()
    assert final["tiers"] == ["basico", "intermedio", "avanzado"] and final["next_tier"] is None
    assert _prueba(c, h, ruta["id"]).status_code == 409


def test_el_plan_y_el_prompt_llevan_lo_estudiado():
    plan = plan_passage_test("Teléfonos y sus procesadores", "Teléfonos y sus procesadores",
                             PlacementRound.BASE, ("Procesador", "Memoria RAM"),
                             ("Procesador (núcleos y frecuencia)", "Memoria RAM"))
    assert plan.concepts == ("procesador", "memoria ram") and plan.round == PlacementRound.BASE
    assert all(r.concepts == plan.concepts for r in plan.rungs)
    sistema = TutorPolicy().generate_diagnostic(plan).system
    assert "PRUEBA DE PASO" in sistema and "Procesador (núcleos y frecuencia)" in sistema
    # La nivelación inicial no cambia: sin lo estudiado, no es prueba de paso.
    assert "PRUEBA DE PASO" not in TutorPolicy().generate_diagnostic(plan_diagnostic("x")).system


def test_no_se_puede_reenviar_la_prueba_tras_ver_las_correctas(entorno):  # noqa: F811
    """ADR-043: el intento muestra las correctas; reenviar la misma prueba perfecta
    subía de nivel sin saber el tema. Solo cuenta el primer intento."""
    c, _ = entorno
    h = _auth(c)
    _nivelarse(c, h, "python", bien=False)
    ruta = _ruta(c, h, "python")
    _completar(c, h, ruta["id"])
    prueba = _prueba(c, h, ruta["id"]).json()
    url = f"/api/v1/quizzes/{prueba['id']}/attempts"

    primero = c.post(url, headers=h, json={"answers": _fallar(prueba)}).json()
    reenvio = c.post(url, headers=h, json={"answers": _correctas(prueba)})

    assert primero["placement"]["level"] == "basico"
    assert reenvio.status_code == 409
    perfil_ruta = c.get(f"/api/v1/learning/paths/{ruta['id']}", headers=h).json()
    assert perfil_ruta["tiers"] == ["basico"], "el reenvío no puede abrir el tramo"


def test_tampoco_se_reenvia_la_nivelacion_inicial(entorno):  # noqa: F811
    c, _ = entorno
    h = _auth(c)
    q = c.post("/api/v1/quizzes/diagnostic", headers=h, json={"topic": "python"}).json()
    url = f"/api/v1/quizzes/{q['id']}/attempts"
    assert c.post(url, headers=h, json={"answers": _fallar(q)}).status_code == 200
    assert c.post(url, headers=h, json={"answers": _correctas(q)}).status_code == 409


def test_la_prueba_de_paso_tiene_limite_de_peticiones():
    from src.infrastructure.rate_limit import _match_rule

    regla = _match_rule("/api/v1/learning/paths/abc/passage-test", "POST")
    assert regla is not None and regla[0] == "ia:passage" and regla[1] <= 6
