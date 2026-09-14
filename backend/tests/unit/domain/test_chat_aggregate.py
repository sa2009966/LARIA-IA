import pytest
from uuid import uuid4

from src.domain.aggregates.chat import ChatAggregate, ChatMessage


class TestChatAggregate:

    def test_create_defaults(self):
        owner = uuid4()
        chat = ChatAggregate.create(owner_id=owner)
        assert chat.owner_id == owner
        assert chat.title == "Nuevo chat"
        assert chat.document_id is None
        assert chat.messages == []
        assert chat.id is not None

    def test_create_custom_title(self):
        owner = uuid4()
        chat = ChatAggregate.create(owner_id=owner, title="Grafos")
        assert chat.title == "Grafos"

    def test_create_empty_title_falls_back(self):
        owner = uuid4()
        chat = ChatAggregate.create(owner_id=owner, title="   ")
        assert chat.title == "Nuevo chat"

    def test_create_title_max_200(self):
        owner = uuid4()
        long_title = "a" * 500
        chat = ChatAggregate.create(owner_id=owner, title=long_title)
        assert len(chat.title) == 200

    def test_create_with_document_id(self):
        owner = uuid4()
        doc_id = uuid4()
        chat = ChatAggregate.create(owner_id=owner, document_id=doc_id)
        assert chat.document_id == doc_id

    def test_add_message_user(self):
        chat = ChatAggregate.create(owner_id=uuid4())
        msg = chat.add_message(role="user", content="Hola")
        assert msg.role == "user"
        assert msg.content == "Hola"
        assert len(chat.messages) == 1
        assert chat.updated_at >= chat.created_at

    def test_add_message_with_metadata(self):
        chat = ChatAggregate.create(owner_id=uuid4())
        chat.add_message(role="user", content="Pregunta", metadata={"document_id": str(uuid4())})
        assert chat.messages[0].metadata == {"document_id": chat.messages[0].metadata["document_id"]}

    def test_add_message_empty_raises(self):
        chat = ChatAggregate.create(owner_id=uuid4())
        with pytest.raises(ValueError, match="vacío"):
            chat.add_message(role="user", content="   ")

    def test_set_title(self):
        chat = ChatAggregate.create(owner_id=uuid4())
        chat.set_title("Nuevo título")
        assert chat.title == "Nuevo título"

    def test_set_title_empty_raises(self):
        chat = ChatAggregate.create(owner_id=uuid4())
        with pytest.raises(ValueError, match="vacío"):
            chat.set_title("   ")

    def test_link_document(self):
        chat = ChatAggregate.create(owner_id=uuid4())
        doc_id = uuid4()
        chat.link_document(doc_id)
        assert chat.document_id == doc_id

    def test_multiple_messages_order(self):
        chat = ChatAggregate.create(owner_id=uuid4())
        chat.add_message(role="user", content="Primer")
        chat.add_message(role="assistant", content="Segundo")
        chat.add_message(role="user", content="Tercer")
        assert [m.content for m in chat.messages] == ["Primer", "Segundo", "Tercer"]
        assert [m.role for m in chat.messages] == ["user", "assistant", "user"]
