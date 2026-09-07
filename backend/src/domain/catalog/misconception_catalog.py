"""Catálogo de misconceptions pedagógicas (álgebra primero).

Los `anchor_concept` son claves de `PrerequisiteGraph` (tras `canonicalize_concept`).
No sustituye al grafo ni a `canonicalize_concept`.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.domain.concept_identity import canonicalize_concept


@dataclass(frozen=True)
class MisconceptionEntry:
    id: str
    subject: str
    anchor_concept: str
    aliases: tuple[str, ...]
    remediation_strategy: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "anchor_concept", canonicalize_concept(self.anchor_concept))
        folded = tuple(canonicalize_concept(a) for a in self.aliases if a and a.strip())
        object.__setattr__(self, "aliases", folded)


# Semilla álgebra alineada a nodos de PrerequisiteGraph (existentes + expansión F4).
ALGEBRA_MISCONCEPTIONS: tuple[MisconceptionEntry, ...] = (
    MisconceptionEntry(
        id="algebra.variable-as-label",
        subject="algebra",
        anchor_concept="variable",
        aliases=(
            "variable como etiqueta",
            "la letra es solo una etiqueta",
            "x es el nombre",
            "confundir variable con etiqueta",
        ),
        remediation_strategy="contrast",
    ),
    MisconceptionEntry(
        id="algebra.adding-unlike-terms",
        subject="algebra",
        anchor_concept="expresión algebraica",
        aliases=(
            "sumar x con numeros",
            "juntar terminos distintos",
            "3x + 2 = 5x",
            "sumar terminos no semejantes",
        ),
        remediation_strategy="counterexample",
    ),
    MisconceptionEntry(
        id="algebra.like-terms-drop-variable",
        subject="algebra",
        anchor_concept="términos semejantes",
        aliases=(
            "solo sumar coeficientes y olvidar la variable",
            "3x+2x=5",
            "perder la variable al combinar",
        ),
        remediation_strategy="worked_example",
    ),
    MisconceptionEntry(
        id="algebra.distributive-partial",
        subject="algebra",
        anchor_concept="propiedad distributiva",
        aliases=(
            "olvidar distribuir al segundo termino",
            "2(x+3)=2x+3",
            "distributiva incompleta",
            "no distribuir a todos",
        ),
        remediation_strategy="scaffold_steps",
    ),
    MisconceptionEntry(
        id="algebra.equals-as-operation",
        subject="algebra",
        anchor_concept="ecuación",
        aliases=(
            "el igual es hacer la operacion",
            "igual como operador",
            "el igual significa el resultado",
            "confundir igualdad con operacion",
        ),
        remediation_strategy="contrast",
    ),
    MisconceptionEntry(
        id="algebra.moving-terms-wrong-sign",
        subject="algebra",
        anchor_concept="resolver ecuación",
        aliases=(
            "pasar el termino sin cambiar el signo",
            "confundir el signo al despejar",
            "mover x y dejar el signo",
            "despejar sin cambiar signo",
        ),
        remediation_strategy="scaffold_steps",
    ),
    MisconceptionEntry(
        id="algebra.cross-multiply-always",
        subject="algebra",
        anchor_concept="ecuaciones lineales",
        aliases=(
            "siempre cruzar multiplicar",
            "producto cruzado en toda ecuacion",
            "cross multiply siempre",
        ),
        remediation_strategy="counterexample",
    ),
    MisconceptionEntry(
        id="algebra.inequality-flip",
        subject="algebra",
        anchor_concept="desigualdad",
        aliases=(
            "no invertir desigualdad al multiplicar por negativo",
            "olvidar voltear la desigualdad",
            "multiplicar desigualdad por menos",
        ),
        remediation_strategy="counterexample",
    ),
)


class MisconceptionCatalog:
    """Colección inmutable de misconceptions; álgebra por defecto."""

    def __init__(self, entries: tuple[MisconceptionEntry, ...] | None = None) -> None:
        self._entries = entries if entries is not None else ALGEBRA_MISCONCEPTIONS

    @property
    def entries(self) -> tuple[MisconceptionEntry, ...]:
        return self._entries

    def get(self, misconception_id: str) -> MisconceptionEntry | None:
        for entry in self._entries:
            if entry.id == misconception_id:
                return entry
        return None

    def __iter__(self):
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)
