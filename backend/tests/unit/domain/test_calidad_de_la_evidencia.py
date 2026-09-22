"""La evidencia sabe de qué concepto habla (fase 4 del plan de corrección).

Toda la ponderación fina del ADR-007 se calcula sobre conceptos que decide un
puñado de heurísticas. Si esas heurísticas inventan conceptos, cruzan materias
o no reconocen al alumno, medir con precisión algo mal etiquetado no da
precisión. Esto blinda los cuatro arreglos.
"""
from uuid import uuid4

from src.domain.aggregates.student_profile import StudentProfile
from src.domain.services.concept_tagger import ConceptTagger
from src.domain.services.learning_signal_detector import (
    LearningSignalDetector,
    LearningSignalKind,
)
from src.domain.services.pedagogical_engine import PedagogicalEngine, TutorIntent
from src.domain.subject_areas import EXACTAS, SOCIALES, area_of_subject
from src.domain.value_objects.question import Difficulty, QuizQuestion


def pregunta(texto: str, opciones: dict[str, str] | None = None) -> QuizQuestion:
    return QuizQuestion(
        text=texto,
        options=opciones or {"A": "una", "B": "otra"},
        correct_answer="A",
        difficulty=Difficulty.MEDIUM,
    )


# --- 4.1: no se inventan conceptos -------------------------------------------------


def test_un_item_irreconocible_se_queda_sin_etiquetar():
    """Antes se le colgaba un concepto llamado "general".

    Ese concepto fantasma entraba a `mastery_by_concept` como cualquier otro:
    engordaba el perfil, competía por el foco y podía llegar al gate.
    """
    etiquetada = ConceptTagger().tag_question(pregunta("¿Cuál de estas opciones es correcta?"))

    assert etiquetada.concept_tags == ()


def test_las_etiquetas_del_modelo_mandan_sobre_la_heuristica():
    original = QuizQuestion(
        text="Si 2x + 3 = 7, ¿cuánto vale x?",
        options={"A": "2", "B": "5"},
        correct_answer="A",
        concept_tags=("ecuaciones lineales",),
    )

    assert ConceptTagger().tag_question(original).concept_tags == ("ecuaciones lineales",)


def test_sin_heuristica_se_usa_el_concepto_del_documento():
    etiquetada = ConceptTagger().tag_question(
        pregunta("¿Cuál de estas opciones es correcta?"),
        document_concepts=("fotosíntesis",),
    )

    assert etiquetada.concept_tags == ("fotosintesis",)


# --- 4.2: las materias no se cruzan ------------------------------------------------


def test_desigualdad_significa_cosas_distintas_segun_la_materia():
    """El hallazgo E7: un alumno de álgebra acumulaba evidencia en sociología."""
    detector = LearningSignalDetector()

    algebra = detector.detect("no entiendo las desigualdades", subject="Matemática")
    historia = detector.detect("no entiendo las desigualdades", subject="Historia")

    assert "desigualdad" in algebra.concepts_hint
    assert "desigualdad social" not in algebra.concepts_hint
    assert "desigualdad social" in historia.concepts_hint


def test_sin_materia_no_se_filtra_nada():
    """Opción segura: quien no conoce el documento recibe todas las heurísticas."""
    hints = LearningSignalDetector().detect("no entiendo las desigualdades").concepts_hint

    assert "desigualdad social" in hints


def test_el_tagger_tambien_respeta_la_materia():
    tagger = ConceptTagger()
    texto = "¿Qué mide la desigualdad en la región?"

    en_matematica = tagger.tag_question(pregunta(texto), subject="Matemática")
    en_historia = tagger.tag_question(pregunta(texto), subject="Historia")

    assert "desigualdad social" not in en_matematica.concept_tags
    assert "desigualdad social" in en_historia.concept_tags


def test_areas_conocidas_y_desconocidas():
    assert area_of_subject("Matemática") == EXACTAS
    assert area_of_subject("Física") == EXACTAS
    assert area_of_subject("Historia") == SOCIALES
    assert area_of_subject("Artística") is None
    assert area_of_subject(None) is None


# --- 4.3: la pregunta lidera el foco -----------------------------------------------


def test_el_tema_preguntado_encabeza_el_foco():
    """Antes el prompt decía "foco: pobreza" mientras preguntaban por derivadas."""
    doc = uuid4()
    profile = StudentProfile.create(uuid4())
    for _ in range(2):
        # Debilidad medida en otro tema, que NO es prerrequisito de lo preguntado.
        profile.record_concept_result("pobreza", 0.1)

    decision = PedagogicalEngine().select(
        profile,
        doc,
        TutorIntent.ASK,
        ("derivadas", "pobreza"),
        question="¿cómo se calculan las derivadas?",
    )

    assert decision.focus_concepts[0] == "derivadas"
    # La debilidad no desaparece: acompaña, no sustituye.
    assert "pobreza" in decision.focus_concepts


def test_un_hueco_medido_y_repetido_sigue_liderando_con_la_base():
    """La pregunta lidera, pero no por encima de `SEQUENCE` (ADR-006).

    Si el alumno pregunta por derivadas y tiene un hueco medido y repetido en
    funciones —su prerrequisito—, el turno sigue empezando por la base, y el
    prompt explica por qué. Esa es la única desviación de foco permitida.
    """
    doc = uuid4()
    profile = StudentProfile.create(uuid4())
    for _ in range(2):
        profile.record_concept_result("funciones", 0.1)

    decision = PedagogicalEngine().select(
        profile,
        doc,
        TutorIntent.ASK,
        ("derivadas", "funciones"),
        question="¿cómo se calculan las derivadas?",
    )

    assert decision.blocked_by_prereq is True
    assert decision.focus_concepts[0] == "funciones"
    assert "derivadas" in decision.objective  # se promete volver al tema


def test_si_la_pregunta_no_nombra_nada_mandan_las_debilidades():
    doc = uuid4()
    profile = StudentProfile.create(uuid4())
    for _ in range(2):
        profile.record_concept_result("funciones", 0.1)

    decision = PedagogicalEngine().select(
        profile, doc, TutorIntent.ASK, ("derivadas",), question="¿me explicas esto?"
    )

    assert decision.focus_concepts[0] == "funciones"


def test_no_se_inventan_conceptos_desde_el_texto_libre():
    """Solo lidera lo que el material declara: el texto libre no crea conceptos."""
    doc = uuid4()

    decision = PedagogicalEngine().select(
        StudentProfile.create(uuid4()),
        doc,
        TutorIntent.ASK,
        ("derivadas",),
        question="¿qué es la termodinámica cuántica?",
    )

    assert "termodinamica cuantica" not in decision.focus_concepts


# --- 4.4: el detector reconoce cómo habla la gente ---------------------------------


def test_formas_reales_de_decir_que_no_entiendes():
    detector = LearningSignalDetector()
    for frase in (
        "no logro captarlo",
        "no me entra esto",
        "sigo sin entender",
        "me perdi en el segundo paso",
        "ni idea de como sigue",
        "me cuesta mucho",
    ):
        assert detector.detect(frase).kind == LearningSignalKind.CONFUSION, frase


def test_pedir_ayuda_en_varias_formas():
    detector = LearningSignalDetector()
    for frase in (
        "dame una pista",
        "explicamelo mas facil",
        "me lo explicas paso a paso?",
        "me podes ayudar con esto",
    ):
        assert detector.detect(frase).kind == LearningSignalKind.HELP, frase


def test_novato_en_varias_formas():
    detector = LearningSignalDetector()
    for frase in (
        "no se nada de esto",
        "es la primera vez que lo veo",
        "recien empiezo con el tema",
        "soy principiante",
    ):
        assert detector.detect(frase).kind == LearningSignalKind.NOVICE, frase


def test_una_pregunta_normal_no_dispara_senal():
    """Sensibilidad no es paranoia: preguntar bien no es pedir auxilio."""
    detector = LearningSignalDetector()
    for frase in (
        "¿cuál es la propiedad distributiva?",
        "¿me das un ejemplo de ecuación lineal?",
        "quiero practicar derivadas",
    ):
        assert detector.detect(frase).kind == LearningSignalKind.NONE, frase
