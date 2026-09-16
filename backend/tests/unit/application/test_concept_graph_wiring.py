"""El grafo persistido llega al tutor y solo el servicio lo escribe (ADR-005)."""
from uuid import uuid4

import pytest

from src.application.services.analyze_document_service import AnalyzeDocumentService
from src.domain.aggregates.concept_graph import EdgeSource
from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.services.pedagogical_engine import TutorIntent
from src.domain.services.prerequisite_graph import GateAction
from src.domain.value_objects.analysis_result import AnalysisResult
from src.infrastructure.persistence.in_memory_concept_graph_repo import (
    InMemoryConceptGraphRepository,
)
from src.infrastructure.persistence.in_memory_document_repo import (
    InMemoryDocumentRepository,
)
from src.infrastructure.persistence.in_memory_student_profile_repo import (
    InMemoryStudentProfileRepository,
)
from src.infrastructure.persistence.in_memory_tutor_interaction_repo import (
    InMemoryTutorInteractionRepository,
)


class StubAnalyst:
    async def analyze(self, document):  # pragma: no cover - no usado aquí
        raise NotImplementedError

    async def generate_quiz(self, *a, **kw):  # pragma: no cover - no usado aquí
        raise NotImplementedError

    async def answer_question(self, context, question, decision=None, adaptation=None):
        return "Respuesta del tutor."


async def _build(key_concepts=()):
    student_id = uuid4()
    doc_repo = InMemoryDocumentRepository()
    document = DocumentAggregate.upload(
        student_id, "alg.txt", "Contenido de álgebra.", "Matemática"
    )
    if key_concepts:
        document.complete_analysis(
            AnalysisResult(
                summary="resumen",
                key_concepts=list(key_concepts),
                suggested_questions=[],
            )
        )
    await doc_repo.save(document)

    graph_repo = InMemoryConceptGraphRepository()
    service = AnalyzeDocumentService(
        document_repository=doc_repo,
        ia_analyst=StubAnalyst(),
        interaction_repository=InMemoryTutorInteractionRepository(),
        profile_repository=InMemoryStudentProfileRepository(),
        concept_graph_repository=graph_repo,
    )
    return service, graph_repo, document, student_id


@pytest.mark.asyncio
async def test_el_grafo_se_siembra_en_el_primer_turno():
    service, graph_repo, document, student_id = await _build()
    assert await graph_repo.find_by_id("default") is None

    await service.prepare_pedagogy(document.id, "¿qué es una variable?", student_id)

    graph = await graph_repo.find_by_id("default")
    assert graph is not None
    assert "funciones" in graph.prerequisites_of("derivadas")


@pytest.mark.asyncio
async def test_la_curacion_docente_llega_a_la_decision():
    """El motor ve la arista curada desde el repositorio.

    Sin evidencia sobre `pobreza` no bloquea (ADR-006): la arista se nota en la
    remediación y en la acción del gate, no en un desvío del foco.
    """
    service, graph_repo, document, student_id = await _build(
        key_concepts=("indice de gini",)
    )
    antes = await service.prepare_pedagogy(document.id, "¿qué es el gini?", student_id)
    assert antes.decision.gate_action == GateAction.PROCEED
    assert antes.decision.remediation_concepts == ()

    graph = await graph_repo.find_by_id("default")
    graph.curate("indice de gini", "pobreza")
    await graph_repo.save(graph)

    plan = await service.prepare_pedagogy(document.id, "¿qué es el gini?", student_id)

    assert plan.decision.gate_action == GateAction.INTEGRATE
    assert "pobreza" in plan.decision.remediation_concepts
    # El alumno sigue recibiendo respuesta a SU pregunta.
    assert plan.decision.focus_concepts[0] == "indice de gini"
    assert plan.decision.blocked_by_prereq is False


@pytest.mark.asyncio
async def test_los_conceptos_del_documento_entran_como_sugerencia():
    service, graph_repo, document, student_id = await _build(
        key_concepts=("pobreza", "desigualdad social")
    )

    plan = await service.prepare_pedagogy(document.id, "¿qué es la pobreza?", student_id)

    graph = await graph_repo.find_by_id("default")
    inferidas = {(e.concept, e.prerequisite) for e in graph.suggestions()}
    assert ("desigualdad social", "pobreza") in inferidas
    # Una sugerencia nunca bloquea: es orden de maquetación, no currículum.
    assert plan.decision.blocked_by_prereq is False


@pytest.mark.asyncio
async def test_sin_repositorio_de_grafo_el_turno_sigue_funcionando():
    """El grafo es opcional: su ausencia no puede tumbar la tutoría."""
    student_id = uuid4()
    doc_repo = InMemoryDocumentRepository()
    document = DocumentAggregate.upload(student_id, "a.txt", "Texto.", "Matemática")
    await doc_repo.save(document)
    service = AnalyzeDocumentService(
        document_repository=doc_repo,
        ia_analyst=StubAnalyst(),
        interaction_repository=InMemoryTutorInteractionRepository(),
        profile_repository=InMemoryStudentProfileRepository(),
    )

    plan = await service.prepare_pedagogy(document.id, "hola", student_id)

    assert plan.decision is not None


@pytest.mark.asyncio
async def test_el_conflicto_de_version_no_rompe_el_turno():
    """La sugerencia perdida se vuelve a proponer; el turno no falla."""
    service, graph_repo, document, student_id = await _build(
        key_concepts=("pobreza", "desigualdad social")
    )
    await service.prepare_pedagogy(document.id, "q", student_id)

    # Otro escritor avanza la versión entre la lectura y la escritura.
    otro = await graph_repo.find_by_id("default")
    otro.curate("informalidad laboral", "pobreza")
    await graph_repo.save(otro)

    graph = await graph_repo.find_by_id("default")
    graph.version = 0  # simula el agregado obsoleto en mano del servicio
    await service._save_graph(graph)

    plan = await service.prepare_pedagogy(document.id, "q", student_id)
    assert plan.decision is not None


@pytest.mark.asyncio
async def test_el_motor_no_muta_el_grafo():
    """El motor lee; escribir es del servicio (ADR-005, Decisión 5)."""
    service, graph_repo, document, student_id = await _build(
        key_concepts=("pobreza", "desigualdad social")
    )
    await service.prepare_pedagogy(document.id, "q", student_id)
    antes = await graph_repo.find_by_id("default")

    engine_graph = await graph_repo.find_by_id("default")
    service._engine.select(
        None,
        document.id,
        TutorIntent.ASK,
        ("pobreza", "gini", "movilidad social"),
        graph=engine_graph,
    )

    assert {(e.concept, e.prerequisite) for e in engine_graph.edges} == {
        (e.concept, e.prerequisite) for e in antes.edges
    }
    assert all(e.source in (EdgeSource.CURATED, EdgeSource.INFERRED) for e in antes.edges)
