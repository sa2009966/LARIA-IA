"""Resuelve una etiqueta de evidencia a id de catálogo (o None si no hay match)."""
from __future__ import annotations

from src.domain.catalog.misconception_catalog import MisconceptionCatalog, MisconceptionEntry
from src.domain.concept_identity import canonicalize_concept


class MisconceptionResolver:
    """Match por id, alias o ancla, siempre vía `canonicalize_concept`."""

    def __init__(self, catalog: MisconceptionCatalog | None = None) -> None:
        self._catalog = catalog or MisconceptionCatalog()
        self._by_id: dict[str, MisconceptionEntry] = {}
        self._by_alias: dict[str, MisconceptionEntry] = {}
        self._by_anchor: dict[str, MisconceptionEntry] = {}
        for entry in self._catalog:
            self._by_id[canonicalize_concept(entry.id)] = entry
            self._by_id[entry.id] = entry
            if entry.anchor_concept and entry.anchor_concept not in self._by_anchor:
                self._by_anchor[entry.anchor_concept] = entry
            for alias in entry.aliases:
                if alias:
                    self._by_alias[alias] = entry

    def resolve(self, label: str) -> str | None:
        entry = self.resolve_entry(label)
        return None if entry is None else entry.id

    def resolve_entry(self, label: str) -> MisconceptionEntry | None:
        key = canonicalize_concept(label)
        if not key:
            return None
        return self._by_id.get(key) or self._by_alias.get(key) or self._by_anchor.get(key)


def resolve_misconception(
    label: str,
    catalog: MisconceptionCatalog | None = None,
) -> str | None:
    """canonicalize_concept(label) + aliases/anchor → catalog.id; None = unmapped."""
    return MisconceptionResolver(catalog).resolve(label)
