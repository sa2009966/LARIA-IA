"""Áreas de conocimiento: a qué familia de conceptos pertenece una materia.

Existe para que las heurísticas de concepto no crucen materias. `desigualdad`
en Matemática es una inecuación; en Historia es desigualdad social. Sin esta
separación, un alumno de álgebra acumulaba evidencia en un concepto de ciencias
sociales que nunca estudió, y esa mezcla contamina mastery, foco y
recomendaciones (ADR-011).

Las materias vienen de la whitelist de `Subject`; lo que no se reconoce no
filtra nada, que es la opción segura: mejor todas las heurísticas que ninguna.
"""
from __future__ import annotations

from src.domain.concept_identity import canonicalize_concept

#: Ciencias exactas: álgebra, cálculo y su aplicación en física/química.
EXACTAS = "exactas"
#: Ciencias sociales y humanidades.
SOCIALES = "sociales"

_AREA_POR_MATERIA: dict[str, str] = {
    "matematica": EXACTAS,
    "matematicas": EXACTAS,
    "fisica": EXACTAS,
    "quimica": EXACTAS,
    "ciencias": EXACTAS,
    "biologia": EXACTAS,
    "historia": SOCIALES,
    "geografia": SOCIALES,
    "filosofia": SOCIALES,
    "lengua": SOCIALES,
    "literatura": SOCIALES,
}


def area_of_subject(subject: object | None) -> str | None:
    """Área de la materia, o None si no se reconoce (⇒ no se filtra nada).

    Acepta el value object `Subject` o una cadena: quien llama no debería tener
    que saber en qué forma viaja la materia.
    """
    if not subject:
        return None
    return _AREA_POR_MATERIA.get(canonicalize_concept(str(subject)))


def matches_area(pattern_area: str | None, subject_area: str | None) -> bool:
    """Si una heurística de un área aplica a un turno de otra.

    Un patrón sin área (neutro) aplica siempre; un turno sin área reconocida
    acepta todos los patrones.
    """
    if pattern_area is None or subject_area is None:
        return True
    return pattern_area == subject_area
