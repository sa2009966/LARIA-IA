"""Etiquetado heurístico de conceptos en ítems de quiz (sin LLM)."""
from __future__ import annotations

import re
import unicodedata

from src.domain.value_objects.question import QuizQuestion

_DEFAULT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bvariables?\b", re.I), "variable"),
    (re.compile(r"\bconstantes?\b", re.I), "constante"),
    (re.compile(r"\becuaci[oó]n(es)?\b|\bdespejar\b|\bresolver\b", re.I), "ecuacion"),
    (re.compile(r"\bdistributiv", re.I), "propiedad distributiva"),
    (re.compile(r"\bexpresi[oó]n(es)?\b", re.I), "expresion algebraica"),
    (re.compile(r"\bsuma\b|\brest(a|ar)\b|\bmultiplic", re.I), "operaciones"),
    # Ciencias sociales / desigualdad LATAM
    (re.compile(r"\bdesigualdad(es)?\b", re.I), "desigualdad social"),
    (re.compile(r"\bpobreza\b|\bindigencia\b", re.I), "pobreza"),
    (re.compile(r"\bgini\b|\bcoeficiente\s+de\s+gini\b", re.I), "indice de gini"),
    (re.compile(r"\bmobilidad\s+social\b|\bmovilidad\s+social\b", re.I), "movilidad social"),
    (re.compile(r"\binformalidad\b|\bempleo\s+informal\b", re.I), "informalidad laboral"),
    (re.compile(r"\beducaci[oó]n\b|\bbrecha\s+educativ", re.I), "brecha educativa"),
    (re.compile(r"\bextractiv", re.I), "extractivismo"),
    (re.compile(r"\blatin\s*am[eé]ric", re.I), "latinoamerica"),
]


def _fold(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


class ConceptTagger:
    """Asigna concept_tags a preguntas usando keywords y conceptos del documento."""

    def __init__(self, extra_patterns: list[tuple[re.Pattern[str], str]] | None = None) -> None:
        self._patterns = list(_DEFAULT_PATTERNS)
        if extra_patterns:
            self._patterns.extend(extra_patterns)

    def tag_question(
        self,
        question: QuizQuestion,
        document_concepts: tuple[str, ...] = (),
    ) -> QuizQuestion:
        if question.concept_tags:
            return question
        blob = _fold(question.text + " " + " ".join(question.options.values()))
        tags: list[str] = []
        for pattern, label in self._patterns:
            if pattern.search(blob) and label not in tags:
                tags.append(label)
        for concept in document_concepts:
            key = concept.strip().lower()
            if not key:
                continue
            if _fold(key) in blob and key not in tags:
                tags.append(key)
        if not tags and document_concepts:
            tags.append(document_concepts[0].strip().lower())
        if not tags:
            tags.append("general")
        return QuizQuestion(
            text=question.text,
            options=dict(question.options),
            correct_answer=question.correct_answer,
            difficulty=question.difficulty,
            concept_tags=tuple(tags[:5]),
        )

    def tag_questions(
        self,
        questions: list[QuizQuestion],
        document_concepts: tuple[str, ...] = (),
    ) -> list[QuizQuestion]:
        return [self.tag_question(q, document_concepts) for q in questions]
