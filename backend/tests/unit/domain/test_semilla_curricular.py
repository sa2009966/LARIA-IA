"""Propiedades de la semilla curricular enriquecida (ADR-005).

El grafo pasó de 19 conceptos a 57 para que el `PrerequisiteGate` tenga sobre
qué escalar: con un currículum somero, la evidencia del estudiante casi nunca
caía sobre un prerrequisito declarado y medio motor era invisible.

Estos tests no comprueban el contenido —eso es currículum, y cambia— sino las
propiedades que hacen que el contenido sirva para algo.
"""
from uuid import uuid4

from src.domain.aggregates.concept_graph import ConceptGraph
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.catalog.prerequisite_seeds import (
    SEED_ALIASES,
    SEED_EDGES,
    build_seeded_graph,
)
from src.domain.services.concept_tagger import _DEFAULT_PATTERNS
from src.domain.services.prerequisite_graph import GateAction, PrerequisiteGate
from src.domain.subject_areas import EXACTAS


# --- Forma del grafo ----------------------------------------------------------------


def test_el_curriculo_tiene_una_sola_raiz():
    """Con varias raíces inconexas, `root_causes` devuelve bases que compiten.

    Una sola entrada hace que la remediación converja siempre a algo concreto
    en vez de ofrecer dos puntos de partida sin relación entre sí.
    """
    graph = build_seeded_graph()

    raices = [c for c in graph.concepts() if not graph.prerequisites_of(c)]

    assert raices == ["numero entero"]


def test_ningun_alias_apunta_al_vacio():
    """Un alias hacia un concepto inexistente canoniza a un nodo huérfano.

    El gate entonces no encuentra prerrequisitos y devuelve PROCEED en silencio:
    el fallo no se nota, solo desaparece la adaptación.
    """
    graph = build_seeded_graph()
    nodos = set(graph.concepts())

    huerfanos = sorted({graph.canonicalize(a) for a in SEED_ALIASES} - nodos)

    assert huerfanos == []


def test_todo_prerrequisito_declarado_existe_como_concepto():
    graph = build_seeded_graph()
    nodos = set(graph.concepts())

    for concepto, prereqs in SEED_EDGES.items():
        assert graph.canonicalize(concepto) in nodos
        for pre in prereqs:
            assert graph.canonicalize(pre) in nodos


# --- El puente con la evidencia real -------------------------------------------------


def test_todo_concepto_que_el_tagger_produce_vive_en_el_grafo():
    """El acoplamiento que de verdad importa, y que estaba roto.

    `ConceptTagger` etiquetaba ítems de quiz como `operaciones`, concepto que el
    grafo no conocía: esa evidencia se medía y no podía gatear nada. Un concepto
    etiquetable que no está en el currículum es evidencia que se tira.
    """
    graph = build_seeded_graph()
    nodos = set(graph.concepts())

    etiquetas_exactas = {
        etiqueta for _, etiqueta, area in _DEFAULT_PATTERNS if area == EXACTAS
    }

    faltan = sorted(e for e in etiquetas_exactas if graph.canonicalize(e) not in nodos)
    assert faltan == []


def test_el_vocabulario_del_material_de_demo_resuelve():
    """Los conceptos tal como los nombra el libro de la demo, no los canónicos."""
    graph = build_seeded_graph()

    for tal_cual, esperado in [
        ("Resolución de ecuaciones", "resolver ecuacion"),
        ("Verificación de resultados", "verificacion de soluciones"),
        ("Expresión algebraica", "expresion algebraica"),
        ("Ecuación", "ecuacion"),
        ("Variable", "variable"),
    ]:
        assert graph.canonicalize(tal_cual) == esperado
        assert esperado in graph.concepts()


# --- Las claves de alias se pliegan --------------------------------------------------


def test_un_alias_con_tilde_resuelve_igual_que_sin_ella():
    """`canonicalize` busca con la clave plegada: sin plegar al guardar, el
    alias acentuado quedaba muerto y nadie se enteraba."""
    graph = ConceptGraph(aliases={"Límites": "límite"})

    assert graph.canonicalize("límites") == "limite"
    assert graph.canonicalize("LIMITES") == "limite"


def test_la_semilla_no_necesita_duplicar_cada_alias_acentuado():
    graph = build_seeded_graph()

    assert graph.canonicalize("álgebra") == graph.canonicalize("algebra") == "variable"
    assert graph.canonicalize("función") == graph.canonicalize("funcion") == "funciones"


# --- Que el gate tenga por fin sobre qué escalar --------------------------------------


def test_fallar_la_aritmetica_secuencia_una_pregunta_de_ecuaciones():
    """El caso que el grafo somero no podía representar.

    `jerarquía de operaciones` no existía, así que fallar repetidamente en
    operaciones no podía explicar por qué el alumno no despeja. Ahora sí.
    """
    graph = build_seeded_graph()
    gate = PrerequisiteGate(graph)
    profile = StudentProfile.create(uuid4())
    for _ in range(2):
        profile.record_concept_result("jerarquía de operaciones", 0.1)

    result = gate.evaluate("resolver ecuación", profile)

    assert result.action == GateAction.SEQUENCE
    assert result.remediation_focus == ("jerarquia de operaciones",)


def test_la_remediacion_ataca_la_raiz_y_no_el_sintoma():
    graph = build_seeded_graph()
    gate = PrerequisiteGate(graph)
    profile = StudentProfile.create(uuid4())
    for concepto in ("operaciones", "igualdad", "propiedades de la igualdad"):
        for _ in range(2):
            profile.record_concept_result(concepto, 0.1)

    result = gate.evaluate("ecuaciones lineales", profile)

    # Los tres son huecos medidos, pero `operaciones` los explica a todos.
    assert set(result.measured_gaps) >= {"operaciones", "igualdad"}
    assert result.remediation_focus == ("operaciones",)
