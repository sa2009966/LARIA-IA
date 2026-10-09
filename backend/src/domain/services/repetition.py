"""Que el tutor no se repita (ADR-040). Pura y determinista.

En producción había 14 pares de respuestas casi iguales a pocos turnos de distancia.
Con la memoria del chat (ADR-021) casi todos desaparecieron, pero quedaban patrones:
"dame más ejemplos" recibía el mismo molde con otros números, la misma muletilla
abría cada respuesta, y cuando el estudiante contestaba un ejercicio ("7", "-1") el
tutor lo resolvía otra vez desde cero, o le decía "¡Muy bien!" aunque estuviera mal.

Aquí solo se reconoce qué está haciendo el estudiante y se dice qué evitar; redactar
sigue siendo cosa del modelo.
"""
from __future__ import annotations

import difflib
import re
import unicodedata

#: Desde aquí dos respuestas se consideran la misma (medido con SequenceMatcher).
REPEATED_REPLY = 0.8
#: Una pregunta así de parecida a una anterior es la misma pregunta otra vez.
REPEATED_QUESTION = 0.85


def _plano(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sin_tildes if not unicodedata.combining(c)).strip()


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _plano(a)[:1500], _plano(b)[:1500]).ratio()


_MAS_EJEMPLOS = re.compile(r"\b(mas|otros?|otra)\s+(ejemplos?|ejercicios?|caso)|\bmas\s+ejemplo|\botro\s+mas\b")
_NO_ENTIENDE = re.compile(
    r"\b(no\s+(lo\s+)?(entiendo|entendi|comprendo|capto|me\s+queda\s+claro)|sigo\s+sin|no\s+le\s+entiendo"
    r"|explica(me|lo|melo)?\s+(de\s+nuevo|otra\s+vez|mejor|de\s+otra\s+forma)|no\s+se\s+entiende)\b"
)
def _es_respuesta_corta(q: str) -> bool:
    """Un número o expresión breve ("7", "-1", "x = 2", "3/4") o una opción ("b").

    "sí" o "ok" no cuentan: contestan a "¿quieres otro ejemplo?", no a un ejercicio.
    """
    q = q.strip().rstrip(".")
    if re.fullmatch(r"[a-d]\)?", q):
        return True
    return len(q) <= 20 and len(q.split()) <= 3 and any(c.isdigit() for c in q)
_PREGUNTA_DEL_TUTOR = re.compile(r"\?\s*$|cu[aá]nto\s+(vale|es|da)|resuelve|calcula|halla|encuentra", re.I | re.M)


def _misma_pregunta(q: str, previa: str) -> bool:
    """Casi igual, o una contenida en la otra: "sobre el teorema de pitagoras" tras
    "Quiero saber sobre el teorema de pitagoras" (caso de producción) da 0.82."""
    if min(len(q), len(previa)) >= 12 and (q in previa or previa in q):
        return True
    return similarity(q, previa) >= REPEATED_QUESTION


def _ultima_del_tutor(history: tuple[tuple[str, str], ...]) -> str:
    return next((t for rol, t in reversed(history) if rol == "assistant"), "")


def _apertura(texto: str, palabras: int = 8) -> str:
    return " ".join(texto.split()[:palabras])


def follow_up_kind(question: str, history: tuple[tuple[str, str], ...]) -> str | None:
    """Qué hace el estudiante respecto a lo anterior: more_examples · not_understood ·
    repeated · answer · None. Sin conversación previa no hay seguimiento."""
    ultima = _ultima_del_tutor(history)
    if not ultima:
        return None
    q = _plano(question)
    if _MAS_EJEMPLOS.search(q):
        return "more_examples"
    if _NO_ENTIENDE.search(q):
        return "not_understood"
    previas = [t for rol, t in history if rol == "user"]
    if any(_misma_pregunta(q, _plano(p)) for p in previas):
        return "repeated"
    if _es_respuesta_corta(q) and _PREGUNTA_DEL_TUTOR.search(ultima):
        return "answer"
    return None


_POR_TIPO = {
    "more_examples": (
        "Pide más ejemplos del tema que están hablando: no le preguntes de qué tema. "
        "Da ejemplos NUEVOS que cambien el TIPO de problema, no solo los números: una "
        "situación de la vida real, buscar el dato que falta en vez del mismo cálculo, o "
        "un caso donde la regla no se cumple. Nada de repetir el ejemplo anterior con "
        "otras cifras."
    ),
    "not_understood": (
        "No entendió tu explicación anterior: no la repitas. Cambia de enfoque (una "
        "analogía cotidiana, más pequeño y paso a paso, o un dibujo descrito) y al final "
        "pregúntale qué parte no le cuadra."
    ),
    "repeated": (
        "Ya te había hecho esta misma pregunta: no repitas tu respuesta. Profundiza o "
        "explícalo por otro ángulo, y pregúntale qué parte quiere aclarar."
    ),
    "answer": (
        "Parece que está respondiendo al ejercicio que le pusiste. Dile primero, con "
        "claridad, si es correcto o no (no digas \"¡Muy bien!\" si está mal). Si falló, "
        "explica el error en una o dos frases y deja que lo intente otra vez; si acertó, "
        "confírmalo sin volver a resolverlo entero y propone el siguiente paso."
    ),
}


def anti_repetition_instruction(question: str, history: tuple[tuple[str, str], ...]) -> str:
    """Lo que el prompt del turno debe evitar. "" sin conversación previa."""
    ultima = _ultima_del_tutor(history)
    if not ultima:
        return ""
    partes = [
        f"Tu respuesta anterior empezaba así: «{_apertura(ultima)}…». No empieces igual "
        "ni repitas su estructura ni sus frases."
    ]
    tipo = follow_up_kind(question, history)
    if tipo:
        partes.append(_POR_TIPO[tipo])
    return " " + " ".join(partes)


def repeats_recent(reply: str, history: tuple[tuple[str, str], ...], last: int = 3) -> bool:
    """Si la respuesta nueva es casi igual a alguna de las últimas `last` del tutor."""
    recientes = [t for rol, t in history if rol == "assistant"][-last:]
    return any(similarity(reply, r) >= REPEATED_REPLY for r in recientes)
