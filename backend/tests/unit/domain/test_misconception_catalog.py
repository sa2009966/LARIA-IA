"""Catálogo de misconceptions y resolución vía canonicalize_concept."""
from src.domain.catalog.misconception_catalog import (
    ALGEBRA_MISCONCEPTIONS,
    MisconceptionCatalog,
)
from src.domain.concept_identity import canonicalize_concept
from src.domain.services.misconception_resolver import (
    MisconceptionResolver,
    resolve_misconception,
)
from src.domain.services.prerequisite_graph import PrerequisiteGraph


def test_algebra_catalog_has_required_fields_and_size():
    catalog = MisconceptionCatalog()
    assert 5 <= len(catalog) <= 10
    for entry in catalog:
        assert entry.id
        assert entry.subject == "algebra"
        assert entry.anchor_concept
        assert entry.aliases
        assert entry.remediation_strategy


def test_catalog_anchors_exist_on_prerequisite_graph():
    graph = PrerequisiteGraph()
    for entry in MisconceptionCatalog():
        key = graph.canonicalize(entry.anchor_concept)
        assert graph.prerequisites_of(key) or graph.successors_of(key), entry.id


def test_resolve_alias_and_accent_to_catalog_id():
    assert resolve_misconception("Confundir el signo al despejar") == (
        "algebra.moving-terms-wrong-sign"
    )
    assert resolve_misconception("ECUACIÓN") == "algebra.equals-as-operation"
    folded = canonicalize_concept("propiedad distributiva")
    assert resolve_misconception(folded) == "algebra.distributive-partial"


def test_resolve_unmapped_returns_none():
    assert resolve_misconception("la revolución francesa") is None
    assert resolve_misconception("") is None
    assert resolve_misconception("   ") is None


def test_resolve_by_catalog_id():
    resolver = MisconceptionResolver()
    assert resolver.resolve("algebra.variable-as-label") == "algebra.variable-as-label"
    entry = resolver.resolve_entry("variable como etiqueta")
    assert entry is not None
    assert entry.anchor_concept == canonicalize_concept("variable")


def test_default_seed_ids_are_stable():
    ids = {e.id for e in ALGEBRA_MISCONCEPTIONS}
    assert "algebra.equals-as-operation" in ids
    assert "algebra.variable-as-label" in ids


def test_catalog_entries_property_exposes_seed():
    catalog = MisconceptionCatalog()
    assert catalog.entries is ALGEBRA_MISCONCEPTIONS
    assert len(catalog.entries) == len(ALGEBRA_MISCONCEPTIONS)


def test_catalog_get_returns_entry_or_none():
    catalog = MisconceptionCatalog()
    hit = catalog.get("algebra.distributive-partial")
    assert hit is not None
    assert hit.remediation_strategy == "scaffold_steps"
    assert catalog.get("algebra.no-such-id") is None


def test_catalog_custom_entries_and_get():
    custom = (ALGEBRA_MISCONCEPTIONS[0],)
    catalog = MisconceptionCatalog(entries=custom)
    assert catalog.entries == custom
    assert catalog.get("algebra.variable-as-label") is custom[0]
    assert catalog.get("algebra.distributive-partial") is None
