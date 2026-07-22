"""Validación y reequilibrio de cuestionarios generados por el LLM.

El modelo tiende a poner casi todas las correctas en 'A'. Eso infla mastery
y rompe la adaptación. LARIA corrige la distribución en dominio, sin otra
llamada al LLM.
"""
from __future__ import annotations

from collections import Counter

from src.domain.value_objects.question import QuizQuestion


class QuizQualityError(ValueError):
    """El cuestionario no cumple criterios mínimos de evidencia fiable."""


def answer_key_distribution(questions: list[QuizQuestion]) -> dict[str, int]:
    return dict(Counter(q.correct_answer.upper() for q in questions))


def is_answer_key_skewed(questions: list[QuizQuestion], *, max_share: float = 0.6) -> bool:
    """True si una sola clave concentra más del max_share de respuestas correctas."""
    if len(questions) < 2:
        return False
    dist = answer_key_distribution(questions)
    dominant = max(dist.values())
    return (dominant / len(questions)) > max_share


def rebalance_answer_keys(questions: list[QuizQuestion]) -> list[QuizQuestion]:
    """Rota opciones de forma determinista para repartir claves correctas.

    No cambia el significado: solo reordena A/B/C/... y actualiza correct_answer.
    """
    if not questions:
        return []

    balanced: list[QuizQuestion] = []
    for index, question in enumerate(questions):
        keys = sorted(question.options.keys())
        n = len(keys)
        if n < 2:
            balanced.append(question)
            continue

        # Rotación acumulativa: pregunta i rota i posiciones.
        shift = index % n
        rotated_keys = keys[shift:] + keys[:shift]
        # Nuevo mapa: A->texto que antes estaba en rotated_keys[0], etc.
        # Queremos etiquetas canónicas A,B,C,... en orden.
        labels = [chr(ord("A") + i) for i in range(n)]
        # Posición de la respuesta correcta en el orden original
        old_correct_idx = keys.index(question.correct_answer)
        # Tras rotar la lista de valores según shift...
        values_in_old_order = [question.options[k] for k in keys]
        rotated_values = values_in_old_order[shift:] + values_in_old_order[:shift]
        new_options = {labels[i]: rotated_values[i] for i in range(n)}
        # La correcta se mueve: old_idx -> (old_idx - shift) mod n en el nuevo orden
        new_correct_idx = (old_correct_idx - shift) % n
        new_correct = labels[new_correct_idx]

        difficulty = question.difficulty
        balanced.append(
            QuizQuestion(
                text=question.text,
                options=new_options,
                correct_answer=new_correct,
                difficulty=difficulty,
            )
        )
    return balanced


def ensure_quiz_quality(questions: list[QuizQuestion]) -> list[QuizQuestion]:
    """Asegura distribución usable; reequilibra si hay sesgo de clave."""
    if not questions:
        raise QuizQualityError("El cuestionario no tiene preguntas")
    for q in questions:
        if len(q.options) < 2:
            raise QuizQualityError("Cada pregunta necesita al menos 2 opciones")
        if q.correct_answer not in q.options:
            raise QuizQualityError("correct_answer inválida")
    if is_answer_key_skewed(questions):
        return rebalance_answer_keys(questions)
    return list(questions)
