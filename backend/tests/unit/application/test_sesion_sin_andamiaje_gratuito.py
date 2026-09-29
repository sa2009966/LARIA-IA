"""Sin evidencia no se andamia, tampoco en el segundo turno (invariante 3).

Cada turno guardaba su respuesta como "pista dada", y el motor andamia cuando hay
pistas dadas. Resultado: desde el segundo mensaje de un chat con libro, todo salía
en modo andamiaje y dificultad fácil, sin que el estudiante hubiera fallado nada.
Ningún test lo comprobaba, y por eso nadie lo vio hasta que "qn sos" gastó el
primer turno y la pregunta real salió andamiada.
"""
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.analyze_document_service import AnalyzeDocumentService
from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.services.pedagogical_engine import PedagogicalMode
from src.domain.value_objects.analysis_result import AnalysisResult
from src.infrastructure.persistence.in_memory_document_repo import InMemoryDocumentRepository
from src.infrastructure.persistence.in_memory_event_bus import InMemoryEventBus
from src.infrastructure.persistence.in_memory_student_profile_repo import (
    InMemoryStudentProfileRepository,
)
from src.infrastructure.persistence.in_memory_tutor_interaction_repo import (
    InMemoryTutorInteractionRepository,
)
from src.infrastructure.persistence.in_memory_tutor_session_repo import (
    InMemoryTutorSessionRepository,
)


@pytest.mark.asyncio
async def test_el_segundo_turno_de_un_alumno_sin_evidencia_no_se_andamia():
    estudiante = uuid4()
    docs = InMemoryDocumentRepository()
    doc = DocumentAggregate.upload(
        estudiante, "algebra.txt", content="Una variable es un valor desconocido.",
        subject="Matemática",
    )
    doc.complete_analysis(AnalysisResult(summary="s", key_concepts=["variable", "ecuación"]))
    await docs.save(doc)
    servicio = AnalyzeDocumentService(
        document_repository=docs,
        ia_analyst=AsyncMock(),
        event_bus=InMemoryEventBus(),
        interaction_repository=InMemoryTutorInteractionRepository(),
        profile_repository=InMemoryStudentProfileRepository(),
        session_repository=InMemoryTutorSessionRepository(),
    )

    primero = await servicio.prepare_pedagogy(doc.id, "¿qué es una variable?", estudiante)
    await servicio.finalize_interaction(primero, "Una variable es una letra que…")
    segundo = await servicio.prepare_pedagogy(doc.id, "¿y una ecuación?", estudiante)

    assert primero.decision.mode == PedagogicalMode.EXPLAIN
    assert segundo.decision.mode != PedagogicalMode.SCAFFOLD, (
        "se andamió sin evidencia: la respuesta anterior contó como pista dada"
    )
