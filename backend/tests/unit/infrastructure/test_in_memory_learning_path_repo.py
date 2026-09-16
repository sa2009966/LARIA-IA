import pytest
from uuid import uuid4

from src.domain.aggregates.learning_path import LearningPathAggregate
from src.infrastructure.persistence.in_memory_learning_path_repo import InMemoryLearningPathRepository


class TestInMemoryLearningPathRepository:

    @pytest.fixture
    def repo(self):
        return InMemoryLearningPathRepository()

    @pytest.mark.asyncio
    async def test_save_and_find_by_id(self, repo):
        path = LearningPathAggregate.create(owner_id=uuid4(), subject="Matemática")
        await repo.save(path)
        found = await repo.find_by_id(path.id)
        assert found is not None
        assert found.id == path.id
        assert found.subject == "Matemática"

    @pytest.mark.asyncio
    async def test_find_by_id_not_found(self, repo):
        assert await repo.find_by_id(uuid4()) is None

    @pytest.mark.asyncio
    async def test_find_by_owner(self, repo):
        owner = uuid4()
        other = uuid4()
        p1 = LearningPathAggregate.create(owner_id=owner, subject="M")
        p2 = LearningPathAggregate.create(owner_id=owner, subject="C")
        p3 = LearningPathAggregate.create(owner_id=other, subject="H")
        await repo.save(p1)
        await repo.save(p2)
        await repo.save(p3)

        paths = await repo.find_by_owner(owner)
        assert len(paths) == 2
        assert {p.subject for p in paths} == {"M", "C"}

    @pytest.mark.asyncio
    async def test_find_by_owner_returns_copies(self, repo):
        owner = uuid4()
        path = LearningPathAggregate.create(owner_id=owner, subject="M")
        await repo.save(path)

        fetched = await repo.find_by_owner(owner)
        fetched[0].record_mastery("x", 0.9)  # mutar copia
        # El original no debe haber cambiado
        original = await repo.find_by_id(path.id)
        assert original.progress == 0.0

    @pytest.mark.asyncio
    async def test_delete(self, repo):
        path = LearningPathAggregate.create(owner_id=uuid4(), subject="M")
        await repo.save(path)
        await repo.delete(path.id)
        assert await repo.find_by_id(path.id) is None

    @pytest.mark.asyncio
    async def test_update_persists(self, repo):
        path = LearningPathAggregate.create(owner_id=uuid4(), subject="M")
        await repo.save(path)
        path.record_mastery("x", 0.9) if path.modules else None
        path.subject = "Matemática avanzada"
        await repo.save(path)

        found = await repo.find_by_id(path.id)
        assert found.subject == "Matemática avanzada"
