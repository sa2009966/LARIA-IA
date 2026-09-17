"""Persistencia del grafo: aislamiento, procedencia y bloqueo optimista."""
import pytest

from src.domain.aggregates.concept_graph import ConceptGraph, EdgeSource
from src.domain.catalog.prerequisite_seeds import build_seeded_graph
from src.domain.exceptions import ConcurrencyError
from src.infrastructure.persistence.in_memory_concept_graph_repo import (
    InMemoryConceptGraphRepository,
)


@pytest.mark.asyncio
async def test_grafo_inexistente_devuelve_none():
    repo = InMemoryConceptGraphRepository()
    assert await repo.find_by_id("default") is None


@pytest.mark.asyncio
async def test_la_semilla_sobrevive_al_viaje():
    repo = InMemoryConceptGraphRepository()
    await repo.save(build_seeded_graph())

    recuperado = await repo.find_by_id("default")

    assert recuperado.canonicalize("función") == recuperado.canonicalize("funciones")
    assert "funciones" in recuperado.prerequisites_of("derivadas")


@pytest.mark.asyncio
async def test_la_procedencia_se_conserva():
    repo = InMemoryConceptGraphRepository()
    graph = ConceptGraph()
    graph.curate("ecuación", "variable")
    graph.suggest("ecuación", "pobreza")
    await repo.save(graph)

    recuperado = await repo.find_by_id("default")

    assert recuperado.prerequisites_of("ecuación") == ("variable",)
    assert len(recuperado.suggestions()) == 1
    assert recuperado.suggestions()[0].source == EdgeSource.INFERRED


@pytest.mark.asyncio
async def test_mutar_lo_recuperado_no_afecta_al_almacen():
    repo = InMemoryConceptGraphRepository()
    await repo.save(ConceptGraph())

    copia = await repo.find_by_id("default")
    copia.curate("ecuación", "variable")

    intacto = await repo.find_by_id("default")
    assert intacto.edges == []


@pytest.mark.asyncio
async def test_save_incrementa_version():
    repo = InMemoryConceptGraphRepository()
    graph = ConceptGraph()
    await repo.save(graph)
    assert graph.version == 1
    await repo.save(graph)
    assert graph.version == 2


@pytest.mark.asyncio
async def test_escritura_con_version_obsoleta_falla():
    repo = InMemoryConceptGraphRepository()
    graph = ConceptGraph()
    await repo.save(graph)

    obsoleto = ConceptGraph(graph_id=graph.graph_id, version=0)
    with pytest.raises(ConcurrencyError):
        await repo.save(obsoleto)
