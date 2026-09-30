"""El tutor recuerda la conversación (memoria de chat).

Los mensajes se guardaban en la base desde el principio, pero **nadie se los
pasaba al modelo**: cada turno se respondía como si fuera el primero. En una
prueba contra producción, un estudiante dijo "me llamo Alex y quiero aprender
historia de Roma", y en el mensaje siguiente el tutor contestó "no tengo acceso a
información personal sobre ti".

Dos reglas sostienen el arreglo:

1. **El historial da continuidad al lenguaje, no decide la pedagogía.** La
   decisión sale de la evidencia. Si el historial entrara en la pregunta, un
   "no entiendo" de hace tres turnos contaría como señal en cada turno.
2. **Tiene tope.** Un chat de doscientos mensajes no puede comerse el
   presupuesto de tokens de cada respuesta.
"""
from unittest.mock import AsyncMock

import pytest

from src.application.services.llm_gate import LlmGate
from src.domain.aggregates.chat import (
    HISTORY_MAX_CHARS,
    HISTORY_MAX_MESSAGES,
    _HISTORY_MAX_PER_MESSAGE,
    ChatMessage,
    recent_history,
)
from src.domain.services.tutor_policy import TutorPolicy


def msg(rol: str, texto: str) -> ChatMessage:
    return ChatMessage(role=rol, content=texto)


# --- Qué parte de la conversación se recuerda -----------------------------------------


def test_se_recuerda_el_dialogo_en_orden():
    historial = recent_history(
        [msg("user", "me llamo Alex"), msg("assistant", "¡Hola, Alex!"), msg("user", "quiero aprender Roma")]
    )

    assert historial == (
        ("user", "me llamo Alex"),
        ("assistant", "¡Hola, Alex!"),
        ("user", "quiero aprender Roma"),
    )


def test_las_notas_y_los_errores_no_son_dialogo():
    """"📎 Subí el archivo" o "no pude generar una respuesta" solo confundirían."""
    historial = recent_history(
        [
            msg("user", "hola"),
            msg("system", "📎 Subí el archivo algebra.pdf"),
            msg("system", "Lo siento, no pude generar una respuesta en este momento."),
            msg("assistant", "¡Hola!"),
        ]
    )

    assert [rol for rol, _ in historial] == ["user", "assistant"]


def test_se_limita_el_numero_de_mensajes_y_se_quedan_los_ultimos():
    mensajes = [msg("user" if i % 2 == 0 else "assistant", f"m{i}") for i in range(40)]

    historial = recent_history(mensajes)

    assert len(historial) == HISTORY_MAX_MESSAGES
    assert historial[-1][1] == "m39", "lo último que se dijo es lo que da continuidad"


def test_se_limita_el_texto_total_sacrificando_lo_mas_antiguo():
    largo = "palabra " * 200
    historial = recent_history([msg("user", largo) for _ in range(8)] + [msg("user", "lo último")])

    assert sum(len(t) for _, t in historial) <= HISTORY_MAX_CHARS
    assert historial[-1][1] == "lo último"


def test_un_mensaje_muy_largo_se_recorta():
    historial = recent_history([msg("assistant", "x " * 2000)])

    assert historial[0][1].endswith("[…]")
    # El tope por mensaje subió de 700 a 1500 con ADR-021; lo que se protege es
    # que haya tope, no su valor.
    assert len(historial[0][1]) <= _HISTORY_MAX_PER_MESSAGE + len(" […]")


def test_el_primer_mensaje_no_tiene_historial():
    assert recent_history([]) == ()


# --- Cómo llega al modelo -------------------------------------------------------------


def test_la_conversacion_va_antes_de_la_pregunta_actual():
    prompt = TutorPolicy().answer_question(
        "", "¿cómo me llamo?", None, history=(("user", "me llamo Alex"), ("assistant", "¡Hola, Alex!"))
    )

    assert "Estudiante: me llamo Alex" in prompt.user
    assert "Tutor: ¡Hola, Alex!" in prompt.user
    # La pregunta a responder sigue siendo la actual, y va al final.
    assert prompt.user.rstrip().endswith("Pregunta: ¿cómo me llamo?")
    assert "continuidad" in prompt.system


def test_sin_historial_el_prompt_no_cambia():
    prompt = TutorPolicy().answer_question("", "hola", None)

    assert "Conversación reciente" not in prompt.user
    assert "continuidad" not in prompt.system


@pytest.mark.asyncio
async def test_la_misma_frase_en_dos_conversaciones_no_comparte_cache():
    """"Las guerras" hablando de Roma no es "las guerras" hablando de Grecia."""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    ia = AsyncMock()
    ia.answer_question_with_model = AsyncMock(return_value="ok")
    gate = LlmGate(ia, cache=cache)

    await gate.answer_question("", "las guerras", None, history=(("user", "quiero aprender Roma"),))
    await gate.answer_question("", "las guerras", None, history=(("user", "quiero aprender Grecia"),))

    claves = {llamada.args[0] for llamada in cache.set.await_args_list}
    assert len(claves) == 2
    # Y la conversación llega de verdad al analista.
    assert ia.answer_question_with_model.await_args.kwargs["history"] == (
        ("user", "quiero aprender Grecia"),
    )


# --- El historial NO decide la pedagogía ----------------------------------------------


@pytest.mark.asyncio
async def test_un_no_entiendo_de_antes_no_vuelve_a_contar_como_senal():
    """Invariante 4: un turno es una observación.

    Si el historial entrara en la detección de señales, el "no entiendo" del
    turno anterior se contaría otra vez en este, y en el siguiente, y así: el
    perfil acabaría registrando dificultad que el estudiante ya no tiene.
    """
    from uuid import uuid4

    from src.application.services.analyze_document_service import AnalyzeDocumentService
    from src.domain.adaptive_signals import SignalKind
    from src.domain.aggregates.document_aggregate import DocumentAggregate
    from src.domain.value_objects.analysis_result import AnalysisResult
    from src.infrastructure.persistence.in_memory_document_repo import InMemoryDocumentRepository
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
        estudiante, "algebra.txt", content="Una variable es un valor.", subject="Matemática"
    )
    doc.complete_analysis(AnalysisResult(summary="s", key_concepts=["variable"]))
    await docs.save(doc)
    servicio = AnalyzeDocumentService(
        document_repository=docs,
        ia_analyst=AsyncMock(),
        event_bus=InMemoryEventBus(),
        interaction_repository=InMemoryTutorInteractionRepository(),
        profile_repository=InMemoryStudentProfileRepository(),
    )

    plan = await servicio.prepare_pedagogy(
        doc.id,
        "¿y cuál es el siguiente paso?",
        estudiante,
        history=(("user", "no entiendo nada, puedes aclarar?"), ("assistant", "Claro…")),
    )

    assert plan.signal_kind == "none", "la dificultad de antes se contó otra vez"
    assert plan.observations.get(SignalKind.CLARIFICATION_RATE, 0.0) == 0.0
    # Pero la conversación sí llega al modelo, que es para lo que está.
    assert plan.history[0] == ("user", "no entiendo nada, puedes aclarar?")
