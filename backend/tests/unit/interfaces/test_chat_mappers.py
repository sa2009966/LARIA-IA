import pytest
from uuid import uuid4

from src.domain.aggregates.chat import ChatAggregate
from src.interfaces.api.routers.chats import _map_chat, _map_summary


class TestChatMappers:

    def test_map_chat_empty(self):
        chat = ChatAggregate.create(owner_id=uuid4(), title="Vacio")
        result = _map_chat(chat)
        assert result.id == str(chat.id)
        assert result.title == "Vacio"
        assert result.document_id is None
        assert result.messages == []

    def test_map_chat_with_messages(self):
        chat = ChatAggregate.create(owner_id=uuid4(), title="Con msgs")
        chat.add_message(role="user", content="Hola")
        chat.add_message(role="assistant", content="Hola, ¿en qué ayudo?")
        result = _map_chat(chat)
        assert len(result.messages) == 2
        assert result.messages[0].role == "user"
        assert result.messages[0].content == "Hola"
        assert result.messages[1].role == "assistant"

    def test_map_chat_with_document(self):
        doc_id = uuid4()
        chat = ChatAggregate.create(owner_id=uuid4(), document_id=doc_id)
        result = _map_chat(chat)
        assert result.document_id == str(doc_id)

    def test_map_summary_no_messages(self):
        chat = ChatAggregate.create(owner_id=uuid4(), title="Sin msgs")
        result = _map_summary(chat)
        assert result.message_count == 0
        assert result.last_message_preview == ""

    def test_map_summary_with_messages(self):
        chat = ChatAggregate.create(owner_id=uuid4(), title="Con msgs")
        chat.add_message(role="user", content="Pregunta corta")
        result = _map_summary(chat)
        assert result.message_count == 1
        assert result.last_message_preview == "Pregunta corta"

    def test_map_summary_preview_truncated(self):
        chat = ChatAggregate.create(owner_id=uuid4())
        long_content = "x" * 200
        chat.add_message(role="user", content=long_content)
        result = _map_summary(chat)
        assert len(result.last_message_preview) == 80
