"""Selecciona contexto acotado al foco conceptual (ahorro de tokens + pedagogía)."""
from __future__ import annotations

import re
import unicodedata

from src.domain.aggregates.document_aggregate import DocumentAggregate


def _fold(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


class ContextSelector:
    """Recorta el documento a summary/conceptos + párrafos alineados al foco."""

    def select(
        self,
        document: DocumentAggregate,
        focus_concepts: tuple[str, ...] = (),
        max_chars: int = 2500,
    ) -> str:
        parts: list[str] = []
        if document.has_analysis() and document.analysis_result is not None:
            ar = document.analysis_result
            if ar.summary:
                parts.append(f"Resumen: {ar.summary}")
            if ar.key_concepts:
                parts.append("Conceptos clave: " + ", ".join(ar.key_concepts[:12]))
        focus = tuple(c.strip().lower() for c in focus_concepts if c and c.strip())
        if focus:
            parts.append("Foco de esta sesión: " + ", ".join(focus))

        content = document.content or ""
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
        if not paragraphs:
            paragraphs = [content.strip()] if content.strip() else []

        selected: list[str] = []
        if focus:
            for para in paragraphs:
                folded = _fold(para)
                if any(_fold(c) in folded for c in focus):
                    selected.append(para)
        if not selected:
            # Sin match: primeras secciones + (si hay) las marcadas como intro
            selected = paragraphs[:3]

        body = "\n\n".join(selected)
        assembled = "\n\n".join(parts + ([body] if body else []))
        if len(assembled) > max_chars:
            return assembled[: max_chars - 20].rstrip() + "\n…[contexto acotado]"
        return assembled
