"""Resuelve una etiqueta de evidencia a id de catálogo (o None si no hay match).

Solo el id y los alias del catálogo resuelven. El **ancla** no: `ecuación` es
el concepto donde vive un malentendido, no el malentendido. Indexar por ancla
convertía "le cuesta X" en "malentiende X de esta forma concreta" y el motor
afirmaba en el prompt un diagnóstico con cero evidencia de él (ADR-007).
"""
from __future__ import annotations

from src.domain.catalog.misconception_catalog import MisconceptionCatalog, MisconceptionEntry
from src.domain.concept_identity import canonicalize_concept


class MisconceptionResolver:
    """Match por id o alias del catálogo, siempre vía `canonicalize_concept`."""

    def __init__(self, catalog: MisconceptionCatalog | None = None) -> None:
        self._catalog = catalog or MisconceptionCatalog()
        self._by_id: dict[str, MisconceptionEntry] = {}
        self._by_alias: dict[str, MisconceptionEntry] = {}
        for entry in self._catalog:
            self._by_id[canonicalize_concept(entry.id)] = entry
            self._by_id[entry.id] = entry
            for alias in entry.aliases:
                if alias:
                    self._by_alias[alias] = entry

    def resolve(self, label: str) -> str | None:
        entry = self.resolve_entry(label)
        return None if entry is None else entry.id

    def resolve_entry(self, label: str) -> MisconceptionEntry | None:
        """Entrada del catálogo, o None si la etiqueta no nombra un malentendido.

        Un concepto suelto (`ecuación`) devuelve None a propósito: el motor lo
        usará como foco sin inventarle un diagnóstico (`unmapped_memory`).
        """
        key = canonicalize_concept(label)
        if not key:
            return None
        return self._by_id.get(key) or self._by_alias.get(key)


def resolve_misconception(
    label: str,
    catalog: MisconceptionCatalog | None = None,
) -> str | None:
    """canonicalize_concept(label) + id/alias → catalog.id; None = unmapped."""
    return MisconceptionResolver(catalog).resolve(label)
