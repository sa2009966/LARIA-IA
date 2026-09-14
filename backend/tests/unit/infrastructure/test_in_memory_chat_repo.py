import pytest
import pytest_asyncio
from uuid import uuid4

from src.domain.aggregates.chat import ChatAggregate
from src.infrastructure.persistence.in_memory_chat_repo import InMemoryChatRepository


@pytest.fixture
def repo():
    return InMemoryChatRepository()


@pytest.fixture
def owner_id():
    return uuid4()


@pytest.fixture
def other_owner_id():
    return uuid4()


class TestInMemoryChatRepository:

    @pytest.mark.asyncio
    async def test_save_and_find_by_id(self, repo, owner_id):
        chat = ChatAggregate.create(owner_id=owner_id, title="Test")
        await repo.save(chat)
        found = await repo.find_by_id(chat.id)
        assert found is not None
        assert found.id == chat.id
        assert found.title == "Test"

    @pytest.mark.asyncio
    async def test_find_by_id_not_found(self, repo):
        found = await repo.find_by_id(uuid4())
        assert found is None

    @pytest.mark.asyncio
    async def test_find_by_owner(self, repo, owner_id, other_owner_id):
        c1 = ChatAggregate.create(owner_id=owner_id, title="Chat 1")
        c2 = ChatAggregate.create(owner_id=owner_id, title="Chat 2")
        c3 = ChatAggregate.create(owner_id=other_owner_id, title="Otro")
        await repo.save(c1)
        await repo.save(c2)
        await repo.save(c3)

        chats = await repo.find_by_owner(owner_id)
        assert len(chats) == 2
        titles = {c.title for c in chats}
        assert titles == {"Chat 1", "Chat 2"}

    @pytest.mark.asyncio
    async def test_find_by_owner_returns_copies_with_messages(self, repo, owner_id):
        chat = ChatAggregate.create(owner_id=owner_id, title="Con mensajes")
        chat.add_message(role="user", content="Hola")
        await repo.save(chat)

        chats = await repo.find_by_owner(owner_id)
        assert len(chats) == 1
        assert len(chats[0].messages) == 1

    @pytest.mark.asyncio
    async def test_find_by_owner_does_not_mutate_persisted_messages(self, repo, owner_id):
        """Regresión: find_by_owner NO debe vaciar los mensajes del chat persistido."""
        chat = ChatAggregate.create(owner_id=owner_id, title="Con mensajes")
        chat.add_message(role="user", content="Hola")
        chat.add_message(role="assistant", content="Hola, ¿en qué ayudo?")
        await repo.save(chat)

        # Listar (summary) → NO debe mutar el objeto guardado
        await repo.find_by_owner(owner_id)

        found = await repo.find_by_id(chat.id)
        assert found is not None
        assert len(found.messages) == 2
        assert found.messages[0].content == "Hola"
        assert found.messages[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_delete(self, repo, owner_id):
        chat = ChatAggregate.create(owner_id=owner_id)
        await repo.save(chat)
        await repo.delete(chat.id)
        assert await repo.find_by_id(chat.id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_no_error(self, repo):
        await repo.delete(uuid4())

    @pytest.mark.asyncio
    async def test_save_updates_existing(self, repo, owner_id):
        chat = ChatAggregate.create(owner_id=owner_id, title="Original")
        await repo.save(chat)
        chat.set_title("Actualizado")
        await repo.save(chat)

        found = await repo.find_by_id(chat.id)
        assert found.title == "Actualizado"
