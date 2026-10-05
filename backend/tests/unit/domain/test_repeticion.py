"""Que el tutor no se repita (ADR-040). Los textos son los de los pares repetidos de producción."""
from uuid import uuid4

import pytest

from src.application.services.chat_tutor_service import ChatTutorService
from src.domain.services.repetition import (
    anti_repetition_instruction,
    follow_up_kind,
    repeats_recent,
)
from src.domain.services.tutor_policy import TutorPolicy

EJERCICIO = (("user", "ponme un ejercicio"), ("assistant", "Resuelve: ¿cuánto vale el límite de 2x + 5 cuando x tiende a 1?"))
PITAGORAS = (("user", "Quiero saber sobre el teorema de pitagoras"),
             ("assistant", "El teorema de Pitágoras establece que en un triángulo rectángulo..."))


@pytest.mark.parametrize("pregunta, tipo", [
    ("ahora dame mas ejemplos", "more_examples"),
    ("Me podrias dar mas ejemplo?", "more_examples"),
    ("no entiendo", "not_understood"),
    ("sigo sin entender", "not_understood"),
    ("explícamelo de otra forma", "not_understood"),
    ("sobre el teorema de pitagoras", "repeated"),
    ("explicame los vectores", None),
])
def test_reconoce_lo_que_hace_el_estudiante(pregunta, tipo):
    assert follow_up_kind(pregunta, PITAGORAS) == tipo


@pytest.mark.parametrize("respuesta", ["7", "-1", "x = 2", "3/4", "b"])
def test_una_respuesta_corta_a_un_ejercicio_es_una_respuesta(respuesta):
    assert follow_up_kind(respuesta, EJERCICIO) == "answer"


def test_si_o_un_numero_sin_ejercicio_no_son_respuestas():
    assert follow_up_kind("sí", EJERCICIO) is None
    assert follow_up_kind("7", (("user", "hola"), ("assistant", "Hola, cuéntame qué quieres aprender."))) is None
    assert follow_up_kind("7", ()) is None


def test_la_instruccion_nombra_la_apertura_y_el_caso():
    inst = anti_repetition_instruction("-1", EJERCICIO)
    assert "«Resuelve: ¿cuánto vale el límite de 2x" in inst
    assert "si es correcto o no" in inst and "¡Muy bien!" in inst
    assert anti_repetition_instruction("hola", ()) == ""


def test_el_prompt_del_chat_lleva_la_instruccion_solo_con_conversacion():
    con = TutorPolicy().answer_question("", "ahora dame mas ejemplos", history=PITAGORAS).system
    assert "no le preguntes de qué tema" in con
    sin = TutorPolicy().answer_question("", "ahora dame mas ejemplos").system
    assert "no le preguntes de qué tema" not in sin


def test_detecta_una_respuesta_casi_igual_a_una_reciente():
    previa = "El teorema de Pitágoras establece que en un triángulo rectángulo, el cuadrado de la hipotenusa..."
    h = (("user", "a"), ("assistant", previa), ("user", "b"), ("assistant", "otra cosa"))
    assert repeats_recent(previa.replace("establece", "dice"), h)
    assert not repeats_recent("Los vectores tienen módulo, dirección y sentido.", h)


class Gate:
    """Primero repite; en el segundo intento, si sabe qué evitar, cambia."""

    def __init__(self, respuestas):
        self.respuestas, self.learners = list(respuestas), []

    async def answer_question(self, **kw):
        self.learners.append(kw.get("learner"))
        return self.respuestas.pop(0)


@pytest.mark.asyncio
async def test_una_respuesta_repetida_se_regenera_una_vez_sabiendo_que_evitar():
    previa = PITAGORAS[1][1]
    gate = Gate([previa, "Piensa en una escalera apoyada en la pared: la escalera es la hipotenusa."])
    r = await ChatTutorService(llm_gate=gate).answer(None, "sobre el teorema de pitagoras", uuid4(), PITAGORAS)
    assert r.content.startswith("Piensa en una escalera")
    assert len(gate.learners) == 2 and gate.learners[1].avoid_reply == previa
    assert "Ibas a responder casi lo mismo" in TutorPolicy().answer_question(
        "", "x", history=PITAGORAS, learner=gate.learners[1]).system


@pytest.mark.asyncio
async def test_solo_se_regenera_una_vez_y_una_respuesta_nueva_no_se_toca():
    previa = PITAGORAS[1][1]
    gate = Gate([previa, previa])
    r = await ChatTutorService(llm_gate=gate).answer(None, "otra vez", uuid4(), PITAGORAS)
    assert r.content == previa and len(gate.learners) == 2
    gate = Gate(["Algo totalmente distinto sobre vectores."])
    await ChatTutorService(llm_gate=gate).answer(None, "vectores", uuid4(), PITAGORAS)
    assert len(gate.learners) == 1
