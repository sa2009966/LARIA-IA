"""El gate escala la intervención con la evidencia (ADR-006).

Invariante central: nunca se desvía el foco en silencio. Solo `SEQUENCE`
lidera con la base, y exige evidencia medida y repetida.
"""
from uuid import uuid4

from src.domain.aggregates.concept_graph import ConceptGraph
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.catalog.prerequisite_seeds import build_seeded_graph
from src.domain.services.prerequisite_graph import GateAction, PrerequisiteGate


def profile_que_domina(*concepts: str) -> StudentProfile:
    profile = StudentProfile.create(uuid4())
    for concept in concepts:
        for _ in range(3):
            profile.record_concept_result(concept, 1.0)
    return profile


def profile_que_falla(*concepts: str, veces: int = 2) -> StudentProfile:
    profile = StudentProfile.create(uuid4())
    for concept in concepts:
        for _ in range(veces):
            profile.record_concept_result(concept, 0.1)
    return profile


# --- Sin evidencia: nunca se bloquea ------------------------------------------------


def test_perfil_vacio_no_bloquea_e_integra():
    """El hallazgo que motivó el ADR-006: la ausencia de dato no es ignorancia."""
    gate = PrerequisiteGate(build_seeded_graph())

    result = gate.evaluate("matrices", None)

    assert result.action == GateAction.INTEGRATE
    assert result.blocked is False
    assert result.measured_gaps == ()
    # La raíz del currículum, no el primer hueco del recorrido. Con el grafo
    # enriquecido esa raíz es `número entero`; lo que el test protege no es la
    # etiqueta sino que sin evidencia se apoye en la base y no bloquee.
    assert result.remediation_focus == ("numero entero",)


def test_perfil_nuevo_tampoco_bloquea():
    gate = PrerequisiteGate(build_seeded_graph())

    result = gate.evaluate("matrices", StudentProfile.create(uuid4()))

    assert result.blocked is False


def test_una_sola_senal_no_alcanza_para_llamarlo_hueco():
    """Coherente con `min_samples_for_adaptation` del ADR-004."""
    gate = PrerequisiteGate(build_seeded_graph(), min_evidence_for_gap=2)
    profile = profile_que_falla("variable", veces=1)

    assert gate.evaluate("matrices", profile).action == GateAction.INTEGRATE


# --- Evidencia medida: se ofrece ----------------------------------------------------

def test_hueco_medido_ofrece_sin_desviar():
    gate = PrerequisiteGate(build_seeded_graph(), error_streak_for_sequence=99)
    profile = profile_que_falla("variable")

    result = gate.evaluate("matrices", profile)

    assert result.action == GateAction.OFFER
    assert result.blocked is False
    assert "variable" in result.measured_gaps


# --- Evidencia medida y repetida: se secuencia --------------------------------------

def test_hueco_repetido_lidera_con_la_base():
    gate = PrerequisiteGate(build_seeded_graph())
    profile = profile_que_falla("variable")

    result = gate.evaluate("matrices", profile)

    assert result.action == GateAction.SEQUENCE
    assert result.blocked is True
    assert result.remediation_focus == ("variable",)


def test_la_raiz_avanza_a_medida_que_se_domina_la_base():
    graph = build_seeded_graph()
    gate = PrerequisiteGate(graph)
    profile = profile_que_domina("variable", "expresión algebraica")
    for _ in range(2):
        profile.record_concept_result("ecuación", 0.1)

    result = gate.evaluate("matrices", profile)

    assert result.action == GateAction.SEQUENCE
    assert result.remediation_focus == (graph.canonicalize("ecuación"),)


# --- Sin huecos ---------------------------------------------------------------------


def test_sin_prerrequisitos_procede():
    """El ejemplo es `número entero` porque es la única raíz del currículum.

    Antes se usaba `variable`, que dejó de ser raíz al enriquecer el grafo: una
    variable representa un número, así que tiene base. La regla que se protege
    —un concepto sin prerrequisitos no tiene nada que gatear— no cambia.
    """
    gate = PrerequisiteGate(build_seeded_graph())
    result = gate.evaluate("número entero", profile_que_domina())
    assert result.action == GateAction.PROCEED
    assert result.remediation_focus == ()


def test_dominar_toda_la_cadena_procede():
    """La cadena se mide entera: basta un eslabón sin dominar para no proceder.

    Con el grafo enriquecido la cadena de `matrices` pasó de 5 conceptos a 13,
    y por eso la lista es larga: el test seguiría pasando en verde con una
    cadena corta sin probar nada. Se construye desde el grafo, no a mano, para
    que siga siendo cierto cuando el currículum crezca otra vez.
    """
    graph = build_seeded_graph()
    gate = PrerequisiteGate(graph)
    profile = profile_que_domina(*graph.all_prerequisites("matrices"))

    assert gate.evaluate("matrices", profile).action == GateAction.PROCEED


def test_dominar_casi_toda_la_cadena_no_procede():
    """El complemento del anterior: sin él, dominar de más pasaría por dominar."""
    graph = build_seeded_graph()
    gate = PrerequisiteGate(graph)
    cadena = graph.all_prerequisites("matrices")
    profile = profile_que_domina(*cadena[1:])  # falta justo la raíz

    assert gate.evaluate("matrices", profile).action != GateAction.PROCEED


# --- Procedencia y grafo ------------------------------------------------------------


def test_una_arista_sugerida_nunca_interviene():
    """Guardarraíl del ADR-005: nadie se ve afectado por lo que no aprobó un humano."""
    graph = ConceptGraph()
    graph.suggest("gini", "pobreza")
    gate = PrerequisiteGate(graph)
    profile = profile_que_falla("pobreza")

    assert gate.evaluate("gini", profile).action == GateAction.PROCEED

    graph.approve("gini", "pobreza")
    assert gate.evaluate("gini", profile).action == GateAction.SEQUENCE


def test_el_grafo_del_parametro_manda_sobre_el_del_constructor():
    """La capa de aplicación pasa el agregado persistido en cada evaluación."""
    persistido = ConceptGraph()
    persistido.curate("gini", "pobreza")
    gate = PrerequisiteGate(ConceptGraph())
    profile = profile_que_falla("pobreza")

    assert gate.evaluate("gini", profile, graph=persistido).action == GateAction.SEQUENCE
    assert gate.evaluate("gini", profile).action == GateAction.PROCEED


def test_remediacion_acotada():
    graph = ConceptGraph()
    for base in ("a", "b", "c", "d", "e", "f"):
        graph.curate("tema", base)
    gate = PrerequisiteGate(graph, max_remediation=4)

    assert len(gate.evaluate("tema", None).remediation_focus) == 4
