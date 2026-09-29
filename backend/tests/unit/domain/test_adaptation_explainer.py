"""El tutor dice por qué habla así (fase C).

Una adaptación que no se explica es indistinguible de la arbitrariedad. Y antes
de eso: es el instrumento que dirá, cuando se apague el modo sombra, si falló la
señal, la política o el arbitraje.
"""
import pytest

from src.domain.adaptive_signals import Signal, SignalKind
from src.domain.services.adaptation_explainer import explain_adaptation
from src.domain.services.adaptive_policy import (
    ControlFlowParameters,
    PromptShapingParameters,
)
from src.domain.services.plan_composer import Override


def senales(**kwargs: float) -> dict[SignalKind, Signal]:
    """Señales con observaciones detrás: `{'self_correction': 0.9}`."""
    return {
        SignalKind(nombre): Signal(kind=SignalKind(nombre), value=valor, samples=10)
        for nombre, valor in kwargs.items()
    }


def forma(**kwargs) -> PromptShapingParameters:
    return PromptShapingParameters(**kwargs)


def flujo(**kwargs) -> ControlFlowParameters:
    return ControlFlowParameters(**kwargs)


# --- Lo básico ---------------------------------------------------------------------


def test_sin_adaptacion_no_se_inventa_un_porque():
    """A un estudiante sin historial no se le explica nada: no hay qué explicar."""
    assert explain_adaptation(forma(), flujo(), {}) == ""


def test_la_frase_nombra_la_conducta_no_la_metrica():
    texto = explain_adaptation(
        forma(explanation_length="short"),
        flujo(),
        senales(long_explanation_abandonment=0.9),
    )

    assert "cuesta arriba" in texto
    # Nada de exponerle nuestras métricas internas al estudiante.
    assert "0.9" not in texto
    assert "long_explanation_abandonment" not in texto
    assert texto.endswith(".") and texto[0].isupper()


def test_sin_senal_detras_no_se_afirma_la_causa():
    """Un parámetro no-default sin señal que lo respalde no genera frase."""
    assert explain_adaptation(forma(explanation_length="short"), flujo(), {}) == ""


# --- Un motivo por parámetro --------------------------------------------------------


@pytest.mark.parametrize(
    "parametros, sus_senales, fragmento",
    [
        ({"explanation_length": "short"}, {"long_explanation_abandonment": 0.9}, "voy al grano"),
        ({"explanation_length": "long"}, {"attention_span": 0.9}, "me extiendo"),
        ({"socratic_question_rate": "high"}, {"self_correction": 0.9}, "te pregunto más"),
        ({"examples_per_explanation": 3}, {"example_request_rate": 0.9}, "3 ejemplos"),
        ({"prefers_analogy": True}, {"analogy_affinity": 0.9}, "analogía"),
    ],
)
def test_cada_parametro_tiene_su_motivo(parametros, sus_senales, fragmento):
    texto = explain_adaptation(forma(**parametros), flujo(), senales(**sus_senales))

    # Sin distinguir mayúsculas: el primer motivo abre la frase y va capitalizado.
    assert fragmento in texto.lower()


def test_el_control_de_flujo_tambien_se_explica():
    texto = explain_adaptation(
        forma(), flujo(chunk_explanation=True), senales(response_latency=0.9)
    )

    assert "por partes" in texto


def test_ofrecer_practica_se_explica_como_forma():
    """Desde el ADR-015 la práctica se ofrece en el prompt, no se orquesta."""
    texto = explain_adaptation(
        forma(practice_before_advance=True), flujo(), senales(practice_seeking=0.9)
    )

    assert "ejercicio antes de seguir" in texto


# --- Los vetos del arbitraje son la mitad interesante -------------------------------


def test_se_explica_lo_que_NO_se_hizo_y_por_que():
    texto = explain_adaptation(
        forma(explanation_length="medium"),
        flujo(),
        senales(long_explanation_abandonment=0.9),
        overrides=(
            Override("explanation_length", "short", "medium", "andamiaje"),
        ),
    )

    assert "no acorto la explicación" in texto.lower()
    assert "base" in texto


# --- Legibilidad --------------------------------------------------------------------


def test_como_mucho_dos_motivos():
    """Explicar, no rendir cuentas: una lista de cinco razones es ruido."""
    texto = explain_adaptation(
        forma(
            explanation_length="short",
            socratic_question_rate="high",
            examples_per_explanation=3,
            prefers_analogy=True,
            practice_before_advance=True,
        ),
        flujo(chunk_explanation=True),
        senales(
            long_explanation_abandonment=0.9,
            self_correction=0.9,
            example_request_rate=0.9,
            analogy_affinity=0.9,
            practice_seeking=0.9,
            response_latency=0.9,
        ),
    )

    assert texto.count(",") <= 2
    assert " y " in texto


# --- El criterio de cierre de la fase -----------------------------------------------


def test_dos_historiales_distintos_dan_dos_frases_distintas_y_correctas():
    """Criterio de cierre: la explicación distingue de verdad a dos estudiantes."""
    quien_abandona = explain_adaptation(
        forma(explanation_length="short"),
        flujo(),
        senales(long_explanation_abandonment=0.9),
    )
    quien_se_autocorrige = explain_adaptation(
        forma(socratic_question_rate="high"),
        flujo(),
        senales(self_correction=0.9),
    )

    assert quien_abandona != quien_se_autocorrige
    assert "voy al grano" in quien_abandona.lower()
    assert "llegar tú a la respuesta" in quien_se_autocorrige.lower()
    # Y ninguna dice lo de la otra: no son plantillas intercambiables.
    assert "llegar tú a la respuesta" not in quien_abandona.lower()
    assert "voy al grano" not in quien_se_autocorrige.lower()


# --- Honestidad: solo se explica lo que de verdad se aplicó -------------------------


async def _plan_de_un_turno_con_senales(adaptation_enabled: bool):
    """Turno real de un estudiante que abandona las explicaciones largas."""
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from src.application.services.analyze_document_service import AnalyzeDocumentService
    from src.domain.aggregates.document_aggregate import DocumentAggregate
    from src.domain.aggregates.student_profile import StudentProfile
    from src.domain.value_objects.analysis_result import AnalysisResult
    from src.infrastructure.persistence.in_memory_document_repo import (
        InMemoryDocumentRepository,
    )
    from src.infrastructure.persistence.in_memory_event_bus import InMemoryEventBus
    from src.infrastructure.persistence.in_memory_student_profile_repo import (
        InMemoryStudentProfileRepository,
    )
    from src.infrastructure.persistence.in_memory_tutor_interaction_repo import (
        InMemoryTutorInteractionRepository,
    )

    estudiante = uuid4()
    docs = InMemoryDocumentRepository()
    doc = DocumentAggregate.upload(
        estudiante, "algebra.txt", content="Una variable es un valor desconocido.",
        subject="Matemática",
    )
    doc.complete_analysis(
        AnalysisResult(summary="s", key_concepts=["variable"], suggested_questions=[])
    )
    await docs.save(doc)

    perfil = StudentProfile.create(estudiante)
    for kind, valor in (
        (SignalKind.LONG_EXPLANATION_ABANDONMENT, 0.95),
        (SignalKind.EXAMPLE_REQUEST_RATE, 0.95),
    ):
        perfil.adaptive_signals[kind.value] = Signal(kind=kind, value=valor, samples=10)
    perfiles = InMemoryStudentProfileRepository()
    await perfiles.save(perfil)

    servicio = AnalyzeDocumentService(
        document_repository=docs,
        ia_analyst=AsyncMock(),
        event_bus=InMemoryEventBus(),
        interaction_repository=InMemoryTutorInteractionRepository(),
        profile_repository=perfiles,
        adaptation_enabled=adaptation_enabled,
    )
    return await servicio.prepare_pedagogy(doc.id, "¿qué es una variable?", estudiante)


@pytest.mark.asyncio
async def test_el_turno_real_explica_su_adaptacion():
    plan = await _plan_de_un_turno_con_senales(adaptation_enabled=True)

    assert plan.explanation
    assert "grano" in plan.explanation.lower() or "ejemplos" in plan.explanation.lower()


@pytest.mark.asyncio
async def test_en_modo_sombra_no_se_promete_lo_que_no_se_hace():
    """La adaptación no llega al prompt: contarla sería mentirle al estudiante."""
    plan = await _plan_de_un_turno_con_senales(adaptation_enabled=False)

    assert plan.explanation == ""
    # La política sí decidió: lo que falta es aplicarlo, no calcularlo.
    assert plan.prompt_shaping.explanation_length == "short"
