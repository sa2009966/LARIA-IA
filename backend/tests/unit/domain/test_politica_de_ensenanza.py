"""TeachingPolicy: las decisiones de la clase son del backend, no del modelo (ADR-028)."""
from uuid import uuid4

import pytest

from src.application.services.teaching_service import validate_syllabus
from src.domain.aggregates.learning_path import (
    CheckOutcome,
    LearningPathAggregate,
    LessonVariant,
    ModuleKind,
    TeachingPhase,
)
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.ports.lesson_generator import SyllabusItem
from src.domain.services.teaching_policy import TeachingPolicy, check_difficulties, outcome_from


def _ruta():
    """base → intermedio → tema (los dos primeros son prerrequisitos)."""
    return LearningPathAggregate.create_for_topic(
        uuid4(),
        "tema",
        "Tema",
        [
            {"concept": "base", "title": "Base", "kind": "prerequisite"},
            {"concept": "intermedio", "title": "Intermedio", "prerequisites": ["base"], "kind": "prerequisite"},
            {"concept": "tema", "title": "Tema", "prerequisites": ["intermedio"], "kind": "content"},
        ],
    )


def _perfil(**resultados):
    """concepto=[ratios de ítems calificados] → evidencia real en el perfil."""
    p = StudentProfile.create(uuid4())
    for concepto, ratios in resultados.items():
        for r in ratios:
            p.record_concept_result(concepto, r)
    return p


def _en_comprobacion(path, concepto, variante=LessonVariant.INTRODUCE, return_to=None):
    path.start_teaching(concepto, variante, return_to=return_to)
    path.deliver_lesson("explicación", "ejemplo", uuid4())


# --- Por dónde empieza ------------------------------------------------------------------


def test_sin_evidencia_de_las_bases_empieza_por_el_tema():
    """No medido ≠ medido en cero (invariante 3): no se enseña lo que nadie midió."""
    paso = TeachingPolicy().next_concept(_ruta(), _perfil())

    assert (paso.phase, paso.concept, paso.variant) == (TeachingPhase.TEACHING, "tema", LessonVariant.INTRODUCE)


def test_una_base_medida_y_floja_se_ensena_antes():
    paso = TeachingPolicy().next_concept(_ruta(), _perfil(base=[0.0, 0.0, 0.0]))

    assert paso.concept == "base"


def test_una_base_medida_y_dominada_se_salta():
    paso = TeachingPolicy().next_concept(_ruta(), _perfil(base=[1.0] * 6, intermedio=[1.0] * 6))

    assert paso.concept == "tema"


def test_dominado_con_nivel_avanzado_es_ruta_completada():
    perfil = _perfil(tema=[1.0] * 8)
    perfil.record_placement("tema", "avanzado")

    assert TeachingPolicy().next_concept(_ruta(), perfil).phase == TeachingPhase.COMPLETED


def test_con_nivel_intermedio_el_contenido_se_ensena_aunque_el_mastery_sea_alto():
    """Dos preguntas medias de la nivelación no prueban el tema: el veredicto
    "intermedio" dice que lo difícil no se demostró."""
    perfil = _perfil(tema=[1.0] * 2)
    perfil.record_placement("tema", "intermedio")

    assert TeachingPolicy().next_concept(_ruta(), perfil).concept == "tema"


# --- Después de la comprobación ---------------------------------------------------------


def test_entender_una_vez_sin_dominar_pide_afianzar():
    """Tras fallos previos, un acierto deja el mastery bajo el umbral (0.658 < 0.7)."""
    path = _ruta()
    _en_comprobacion(path, "tema")
    path.record_check(CheckOutcome.UNDERSTOOD)

    paso = TeachingPolicy().after_check(path, CheckOutcome.UNDERSTOOD, _perfil(tema=[0.0, 0.0, 1.0, 1.0]))

    assert (paso.concept, paso.variant) == ("tema", LessonVariant.CONSOLIDATE)


def test_entender_dos_veces_seguidas_avanza():
    path = _ruta()
    for _ in range(2):
        _en_comprobacion(path, "tema")
        path.record_check(CheckOutcome.UNDERSTOOD)

    paso = TeachingPolicy().after_check(path, CheckOutcome.UNDERSTOOD, _perfil(tema=[1.0] * 4))

    assert paso.phase == TeachingPhase.COMPLETED and "tema" in path.teaching.passed_concepts


def test_entender_a_medias_da_otro_ejemplo():
    path = _ruta()
    _en_comprobacion(path, "tema")
    path.record_check(CheckOutcome.PARTIAL)

    paso = TeachingPolicy().after_check(path, CheckOutcome.PARTIAL, _perfil(tema=[1.0, 0.0]))

    assert (paso.concept, paso.variant) == ("tema", LessonVariant.NEW_EXAMPLE)


def test_no_entender_una_vez_sin_evidencia_de_la_base_reformula():
    path = _ruta()
    _en_comprobacion(path, "tema")
    path.record_check(CheckOutcome.NOT_UNDERSTOOD)

    paso = TeachingPolicy().after_check(path, CheckOutcome.NOT_UNDERSTOOD, _perfil(tema=[0.0, 0.0]))

    assert (paso.concept, paso.variant) == ("tema", LessonVariant.REFORMULATE)


def test_no_entender_con_la_base_medida_y_floja_remedia_la_causa_raiz():
    """El gate decide con evidencia: el desvío va a la base, y se promete volver."""
    path = _ruta()
    _en_comprobacion(path, "tema")
    path.record_check(CheckOutcome.NOT_UNDERSTOOD)
    perfil = _perfil(tema=[0.0, 0.0], base=[0.0, 0.0, 0.0], intermedio=[0.0, 0.0, 0.0])

    paso = TeachingPolicy().after_check(path, CheckOutcome.NOT_UNDERSTOOD, perfil)

    assert paso.phase == TeachingPhase.REMEDIATION and paso.variant == LessonVariant.REMEDIATE
    assert paso.concept == "base", "causa raíz, no el primer síntoma"
    assert paso.return_to == "tema" and "volvemos" in paso.reason


def test_no_entender_dos_veces_remedia_aunque_la_base_no_este_medida():
    path = _ruta()
    for _ in range(2):
        _en_comprobacion(path, "tema")
        path.record_check(CheckOutcome.NOT_UNDERSTOOD)

    paso = TeachingPolicy().after_check(path, CheckOutcome.NOT_UNDERSTOOD, _perfil(tema=[0.0] * 4))

    assert paso.phase == TeachingPhase.REMEDIATION and paso.return_to == "tema"


def test_al_dominar_la_base_se_vuelve_al_tema():
    path = _ruta()
    for _ in range(2):
        _en_comprobacion(path, "base", LessonVariant.REMEDIATE, return_to="tema")
        path.record_check(CheckOutcome.UNDERSTOOD)

    paso = TeachingPolicy().after_check(path, CheckOutcome.UNDERSTOOD, _perfil(base=[1.0] * 4))

    assert (paso.concept, paso.variant) == ("tema", LessonVariant.RESUME)


def test_el_resultado_sale_de_aciertos():
    assert outcome_from(2, 2) == CheckOutcome.UNDERSTOOD
    assert outcome_from(1, 2) == CheckOutcome.PARTIAL
    assert outcome_from(0, 2) == CheckOutcome.NOT_UNDERSTOOD


def test_la_dificultad_de_la_comprobacion_la_fija_el_backend():
    assert [d.value for d in check_difficulties(LessonVariant.CONSOLIDATE)] == ["medium", "hard"]
    assert [d.value for d in check_difficulties(LessonVariant.REFORMULATE)] == ["easy", "easy"]


# --- Agregado -----------------------------------------------------------------------------


def test_sin_comprobacion_pendiente_no_se_registra_resultado():
    with pytest.raises(ValueError):
        _ruta().record_check(CheckOutcome.UNDERSTOOD)


def test_la_proyeccion_da_por_sabidos_los_prerrequisitos_sin_medir():
    path = _ruta()
    path.project_mastery({}, measured=set())

    estados = {m.concept: m.status for m in path.modules}
    assert estados == {"base": "assumed", "intermedio": "assumed", "tema": "available"}


def test_un_prerrequisito_fuera_de_la_ruta_se_descarta():
    p = LearningPathAggregate.create_for_topic(uuid4(), "t", "T", [{"concept": "t", "prerequisites": ["externo"]}])

    assert p.modules[0].prerequisites == []


# --- Temario de temas fuera del grafo ----------------------------------------------------


def test_el_temario_solo_admite_prerrequisitos_anteriores_y_sin_repetidos():
    items = [
        SyllabusItem("Variables", ("Funciones",)),  # apunta hacia delante: se ignora
        SyllabusItem("Funciones", ("Variables",)),
        SyllabusItem("variables"),  # repetido
        SyllabusItem("Bucles", ("Variables", "Inexistente")),
    ]

    mods = validate_syllabus(items, "python", "Python")

    assert [m["concept"] for m in mods] == ["variables", "funciones", "bucles"]
    assert [m["prerequisites"] for m in mods] == [[], ["variables"], ["variables"]]
    assert all(m["kind"] == ModuleKind.CONTENT.value for m in mods)


def test_un_temario_vacio_ensena_el_tema_entero():
    assert [m["concept"] for m in validate_syllabus([], "python", "Python")] == ["python"]


def test_un_acierto_que_ya_domina_el_concepto_avanza_sin_afianzar():
    path = _ruta()
    _en_comprobacion(path, "tema")
    path.record_check(CheckOutcome.UNDERSTOOD)

    paso = TeachingPolicy().after_check(path, CheckOutcome.UNDERSTOOD, _perfil(tema=[1.0, 1.0]))

    assert paso.phase == TeachingPhase.COMPLETED


def test_dos_comprobaciones_superadas_avanzan_aunque_el_mastery_siga_bajo():
    """Sin la racha, quien acierta todo se quedaría comprobando hasta que el promedio suba."""
    path = _ruta()
    for _ in range(2):
        _en_comprobacion(path, "tema")
        path.record_check(CheckOutcome.UNDERSTOOD)

    paso = TeachingPolicy().after_check(path, CheckOutcome.UNDERSTOOD, _perfil(tema=[0.0, 0.0, 1.0, 1.0]))

    assert paso.phase == TeachingPhase.COMPLETED


def test_el_prompt_de_la_leccion_pide_lo_que_decidio_el_backend():
    from src.domain.ports.lesson_generator import LessonRequest
    from src.domain.services.tutor_policy import TutorPolicy
    from src.domain.value_objects.question import Difficulty

    req = LessonRequest(
        topic_label="Fracciones", concept="fraccion", concept_title="Fracciones",
        variant=LessonVariant.CONSOLIDATE, check_difficulties=(Difficulty.MEDIUM, Difficulty.HARD),
        level="basico", avoid_example="pizza de 8 porciones",
    )
    s = TutorPolicy().teaching_lesson(req).system

    assert "«Fracciones» y NO otro" in s
    assert "medium, hard" in s and "EXACTAMENTE 2" in s
    assert "2-3 frases" in s, "afianzar no repite la introducción"
    assert "pizza de 8 porciones" in s, "no se repite el ejemplo"
    assert "UNA sola opción correcta" in s
