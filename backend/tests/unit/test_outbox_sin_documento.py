"""Un intento sin documento (nivelación o práctica) sobrevive al outbox.

`str(None)` se guardaba como "None" y al leerlo `UUID("None")` reventaba fuera
del try del worker: el nivel nunca llegaba al perfil y el evento se reintentaba
sin fin. Hoy producción usa el bus en memoria, así que no mordió; con
EVENT_BUS_BACKEND=outbox, toda nivelación se habría perdido.
"""
from uuid import uuid4

import pytest

from src.domain.events.domain_events import QuizAttemptCompletedEvent
from src.infrastructure.mongodb.outbox_event_bus import _deserialize, _serialize


def _ida_y_vuelta(evento):
    p = _serialize(evento)
    return _deserialize({"event_type": p["event_type"], "payload": p})


def test_nivelacion_sin_documento_vuelve_con_document_id_none():
    e = QuizAttemptCompletedEvent(
        aggregate_id=uuid4(), quiz_id=uuid4(), document_id=None,
        student_id=uuid4(), score=3, total=6,
    )

    leido = _ida_y_vuelta(e)

    assert leido.document_id is None
    assert leido.event_id == e.event_id and leido.score == 3


@pytest.mark.parametrize("guardado", ["None", None, ""])
def test_lee_lo_que_escribia_la_version_anterior(guardado):
    e = QuizAttemptCompletedEvent(
        aggregate_id=uuid4(), quiz_id=uuid4(), document_id=uuid4(),
        student_id=uuid4(), score=1, total=1,
    )
    p = _serialize(e)
    p["document_id"] = guardado

    assert _deserialize({"event_type": p["event_type"], "payload": p}).document_id is None


def test_con_documento_no_cambia():
    doc = uuid4()
    e = QuizAttemptCompletedEvent(
        aggregate_id=uuid4(), quiz_id=uuid4(), document_id=doc,
        student_id=uuid4(), score=1, total=1,
    )

    assert _ida_y_vuelta(e).document_id == doc
