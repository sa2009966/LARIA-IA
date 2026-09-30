"""Interacciones sin documento (nivelación, práctica) sobreviven a Mongo.

Se guardaba `str(None)` = "None" y al leer `UUID("None")` rompía GET /learning/me
con 500 desde la primera nivelación: la sección de aprendizaje del frontend
mostraba "No se pudo cargar tu perfil de aprendizaje" para siempre.
"""
from uuid import uuid4

import pytest

from src.domain.aggregates.tutor_interaction import TutorInteractionAggregate
from src.infrastructure.mongodb.tutor_interaction_repository import (
    MongoDBTutorInteractionRepository as Repo,
)


def test_sin_documento_ida_y_vuelta():
    i = TutorInteractionAggregate.create(student_id=uuid4(), document_id=None, question="[quiz_attempt]", answer="3/6")

    doc = Repo._to_doc(i)

    assert doc["document_id"] is None
    assert Repo._from_doc(doc).document_id is None


@pytest.mark.parametrize("guardado", ["None", None, ""])
def test_lee_lo_que_ya_esta_guardado_en_produccion(guardado):
    i = TutorInteractionAggregate.create(student_id=uuid4(), document_id=uuid4(), question="q", answer="a")
    doc = Repo._to_doc(i)
    doc["document_id"] = guardado

    assert Repo._from_doc(doc).document_id is None


def test_con_documento_no_cambia():
    d = uuid4()
    i = TutorInteractionAggregate.create(student_id=uuid4(), document_id=d, question="q", answer="a")

    assert Repo._from_doc(Repo._to_doc(i)).document_id == d
