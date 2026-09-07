"""Índices Mongo al arranque alineados a docs/mongodb-schema.md."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.mongodb.indexes import ensure_all_indexes


def _collection() -> MagicMock:
    col = MagicMock()
    col.create_index = AsyncMock()
    return col


@pytest.mark.asyncio
async def test_ensure_all_indexes_creates_schema_indexes():
    db = MagicMock()
    db.users = _collection()
    db.documents = _collection()
    db.quizzes = _collection()
    db.quiz_attempts = _collection()
    db.tutor_interactions = _collection()
    db.tutor_sessions = _collection()
    db.student_profiles = _collection()
    db.event_outbox = _collection()
    db.chats = _collection()

    await ensure_all_indexes(db)

    db.users.create_index.assert_any_await("email", unique=True)
    db.users.create_index.assert_any_await("username", unique=True)
    db.documents.create_index.assert_any_await("owner_id")
    db.quizzes.create_index.assert_any_await("document_id")
    db.quizzes.create_index.assert_any_await("owner_id")
    db.quiz_attempts.create_index.assert_any_await("student_id")
    db.quiz_attempts.create_index.assert_any_await("document_id")
    db.tutor_interactions.create_index.assert_any_await("student_id")
    db.tutor_interactions.create_index.assert_any_await("document_id")
    db.tutor_sessions.create_index.assert_any_await("document_id")
    db.tutor_sessions.create_index.assert_any_await(
        [("student_id", 1), ("document_id", 1)],
        unique=True,
    )
    db.event_outbox.create_index.assert_any_await("processed_at")
    db.event_outbox.create_index.assert_any_await(
        [("processed_at", 1), ("created_at", 1)]
    )
    # student_profiles: _id = student_id (PK); sin índice adicional en ensure_all_indexes.
    assert hasattr(db, "student_profiles")
    db.student_profiles.create_index.assert_not_called()
    assert db.users.create_index.await_count == 2
    assert db.quizzes.create_index.await_count == 2
    assert db.quiz_attempts.create_index.await_count == 2
    assert db.tutor_interactions.create_index.await_count == 2
    assert db.tutor_sessions.create_index.await_count == 2
    assert db.event_outbox.create_index.await_count == 2
    assert db.chats.create_index.await_count == 2
    db.chats.create_index.assert_any_await("owner_id")
    db.chats.create_index.assert_any_await("updated_at")
