"""Cobertura MongoDB: database, GridFS, repos pendientes."""
from __future__ import annotations

import pytest
from bson import ObjectId
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.aggregates.quiz_aggregate import QuizAggregate
from src.domain.aggregates.quiz_attempt_aggregate import QuizAttemptAggregate
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.aggregates.tutor_session import TutorSession
from src.domain.exceptions import ConcurrencyError
from src.domain.value_objects.analysis_result import AnalysisResult
from src.domain.value_objects.question import QuizQuestion
from src.infrastructure.mongodb.database import close_database, get_database
from src.infrastructure.mongodb.document_repository import MongoDBDocumentRepository
from src.infrastructure.mongodb.gridfs_document_blob_store import GridFSDocumentBlobStore
from src.infrastructure.mongodb.quiz_attempt_repository import MongoDBQuizAttemptRepository
from src.infrastructure.mongodb.quiz_repository import MongoDBQuizRepository
from src.infrastructure.mongodb.student_profile_repository import MongoDBStudentProfileRepository
from src.infrastructure.mongodb.tutor_interaction_repository import MongoDBTutorInteractionRepository
from src.infrastructure.mongodb.tutor_session_repository import MongoDBTutorSessionRepository

from tests.unit.infrastructure.test_mongodb_repos import AsyncCursorMock


@pytest.fixture
def ext_db():
    db = MagicMock()
    for name in (
        "users",
        "documents",
        "analyses",
        "quizzes",
        "quiz_attempts",
        "tutor_interactions",
        "student_profiles",
        "tutor_sessions",
    ):
        coll = MagicMock()
        coll.find_one = AsyncMock()
        coll.find = MagicMock()
        coll.replace_one = AsyncMock()
        coll.insert_one = AsyncMock()
        coll.delete_one = AsyncMock()
        coll.delete_many = AsyncMock()
        setattr(db, name, coll)
    return db


class TestMongoDatabase:
    @pytest.mark.asyncio
    async def test_get_and_close_database(self):
        import src.infrastructure.mongodb.database as db_mod

        db_mod._client = None
        mock_db = MagicMock()
        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        with patch("src.infrastructure.mongodb.database.AsyncIOMotorClient", return_value=mock_client):
            db = await get_database()
            assert db is mock_db
            db2 = await get_database()
            assert db2 is mock_db

        await close_database()
        assert db_mod._client is None
        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_database_noop_when_not_open(self):
        import src.infrastructure.mongodb.database as db_mod

        db_mod._client = None
        await close_database()
        assert db_mod._client is None


class TestGridFSDocumentBlobStore:
    @pytest.mark.asyncio
    async def test_put_get_delete(self):
        mock_db = MagicMock()
        oid = ObjectId()
        mock_bucket = MagicMock()
        mock_bucket.upload_from_stream = AsyncMock(return_value=oid)

        async def _download(_oid, buf):
            buf.write(b"hello-bytes")

        mock_bucket.download_to_stream = AsyncMock(side_effect=_download)
        mock_bucket.delete = AsyncMock()

        store = GridFSDocumentBlobStore(database=mock_db)
        with patch(
            "src.infrastructure.mongodb.gridfs_document_blob_store.AsyncIOMotorGridFSBucket",
            return_value=mock_bucket,
        ):
            blob_id = await store.put(b"hello-bytes", filename="doc.txt", content_type="text/plain")
            assert blob_id == str(oid)
            data = await store.get(blob_id)
            assert data == b"hello-bytes"
            await store.delete(blob_id)
            mock_bucket.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_invalid_id_raises_key_error(self):
        store = GridFSDocumentBlobStore(database=MagicMock())
        with patch.object(store, "_bucket", AsyncMock(return_value=MagicMock())):
            with pytest.raises(KeyError, match="Blob no encontrado"):
                await store.get("not-an-objectid")

    @pytest.mark.asyncio
    async def test_get_missing_blob_raises_key_error(self):
        mock_bucket = MagicMock()
        mock_bucket.download_to_stream = AsyncMock(side_effect=RuntimeError("missing"))
        store = GridFSDocumentBlobStore(database=MagicMock())
        with patch.object(store, "_bucket", AsyncMock(return_value=mock_bucket)):
            with pytest.raises(KeyError):
                await store.get(str(ObjectId()))

    @pytest.mark.asyncio
    async def test_delete_invalid_id_is_noop(self):
        store = GridFSDocumentBlobStore(database=MagicMock())
        with patch.object(store, "_bucket", AsyncMock(return_value=MagicMock())):
            await store.delete("bad-id")

    @pytest.mark.asyncio
    async def test_delete_missing_blob_swallowed(self):
        mock_bucket = MagicMock()
        mock_bucket.delete = AsyncMock(side_effect=RuntimeError("gone"))
        store = GridFSDocumentBlobStore(database=MagicMock())
        with patch.object(store, "_bucket", AsyncMock(return_value=mock_bucket)):
            await store.delete(str(ObjectId()))

    @pytest.mark.asyncio
    async def test_bucket_lazy_get_database(self):
        store = GridFSDocumentBlobStore()
        mock_db = MagicMock()
        with patch(
            "src.infrastructure.mongodb.gridfs_document_blob_store.get_database",
            AsyncMock(return_value=mock_db),
        ):
            with patch(
                "src.infrastructure.mongodb.gridfs_document_blob_store.AsyncIOMotorGridFSBucket",
            ) as bucket_cls:
                await store._bucket()
                bucket_cls.assert_called_once_with(mock_db)


class TestMongoDBDocumentRepositoryExtended:
    @pytest.mark.asyncio
    async def test_get_content_inline(self, ext_db):
        doc_id = uuid4()
        ext_db.documents.find_one.return_value = {"content": "inline-text"}
        repo = MongoDBDocumentRepository(database=ext_db)
        assert await repo.get_content(doc_id) == "inline-text"

    @pytest.mark.asyncio
    async def test_get_content_from_blob_store(self, ext_db):
        doc_id = uuid4()
        blob_id = str(ObjectId())
        ext_db.documents.find_one.return_value = {"content_blob_id": blob_id}
        blob_store = MagicMock()
        blob_store.get = AsyncMock(return_value=b"blob-body")
        repo = MongoDBDocumentRepository(database=ext_db, blob_store=blob_store)
        assert await repo.get_content(doc_id) == "blob-body"

    @pytest.mark.asyncio
    async def test_get_content_blob_missing_returns_empty(self, ext_db):
        doc_id = uuid4()
        ext_db.documents.find_one.return_value = {"content_blob_id": str(ObjectId())}
        blob_store = MagicMock()
        blob_store.get = AsyncMock(side_effect=KeyError("missing"))
        repo = MongoDBDocumentRepository(database=ext_db, blob_store=blob_store)
        assert await repo.get_content(doc_id) == ""

    @pytest.mark.asyncio
    async def test_get_content_not_found(self, ext_db):
        ext_db.documents.find_one.return_value = None
        repo = MongoDBDocumentRepository(database=ext_db)
        assert await repo.get_content(uuid4()) is None

    @pytest.mark.asyncio
    async def test_delete_removes_blob(self, ext_db):
        doc_id = uuid4()
        blob_id = str(ObjectId())
        ext_db.documents.find_one.return_value = {"content_blob_id": blob_id}
        blob_store = MagicMock()
        blob_store.delete = AsyncMock()
        repo = MongoDBDocumentRepository(database=ext_db, blob_store=blob_store)
        await repo.delete(doc_id)
        blob_store.delete.assert_awaited_once_with(blob_id)

    @pytest.mark.asyncio
    async def test_analysis_result_parsing_edge_cases(self):
        result = MongoDBDocumentRepository._analysis_result_from_doc(
            {
                "summary": "S",
                "key_concepts": [["nested"], "plain"],
                "suggested_questions": [{"text": "Q?"}],
                "confidence_score": 0.5,
            }
        )
        assert result.key_concepts == ["nested", "plain"]
        assert result.suggested_questions == ["Q?"]

    @pytest.mark.asyncio
    async def test_to_doc_with_blob_id_clears_inline_content(self):
        doc = DocumentAggregate.upload(uuid4(), "f.txt", "big", "Historia")
        doc.content_blob_id = str(ObjectId())
        payload = MongoDBDocumentRepository._to_doc(doc)
        assert payload["content"] == ""
        assert payload["content_blob_id"] == doc.content_blob_id


class TestMongoDBStudentProfileRepository:
    @pytest.mark.asyncio
    async def test_save_insert_and_find(self, ext_db):
        student = uuid4()
        profile = StudentProfile.create(student)
        ext_db.student_profiles.find_one.return_value = None
        repo = MongoDBStudentProfileRepository(database=ext_db)
        await repo.save(profile)
        ext_db.student_profiles.insert_one.assert_awaited_once()
        assert profile.version == 1

    @pytest.mark.asyncio
    async def test_save_concurrency_error(self, ext_db):
        student = uuid4()
        profile = StudentProfile.create(student)
        profile.version = 2
        ext_db.student_profiles.replace_one.return_value = MagicMock(matched_count=0)
        repo = MongoDBStudentProfileRepository(database=ext_db)
        with pytest.raises(ConcurrencyError):
            await repo.save(profile)

    @pytest.mark.asyncio
    async def test_find_by_student_roundtrip(self, ext_db):
        student = uuid4()
        profile = StudentProfile.create(student)
        profile.record_quiz_result(uuid4(), 0.8)
        doc = MongoDBStudentProfileRepository._to_doc(profile, version=1)
        ext_db.student_profiles.find_one.return_value = doc
        repo = MongoDBStudentProfileRepository(database=ext_db)
        found = await repo.find_by_student(student)
        assert found is not None
        assert found.student_id == student

    @pytest.mark.asyncio
    async def test_save_version_zero_replace_existing(self, ext_db):
        student = uuid4()
        profile = StudentProfile.create(student)
        ext_db.student_profiles.find_one.return_value = {"version": 0}
        ext_db.student_profiles.replace_one.return_value = MagicMock(matched_count=1)
        repo = MongoDBStudentProfileRepository(database=ext_db)
        await repo.save(profile)
        ext_db.student_profiles.replace_one.assert_awaited()


class TestMongoDBTutorSessionRepository:
    @pytest.mark.asyncio
    async def test_save_find_delete(self, ext_db):
        student = uuid4()
        doc_id = uuid4()
        session = TutorSession.start(student, doc_id, objective="obj", focus_concepts=("x",))
        ext_db.tutor_sessions.find_one.return_value = None
        repo = MongoDBTutorSessionRepository(database=ext_db)
        await repo.save(session)
        ext_db.tutor_sessions.insert_one.assert_awaited_once()

        payload = MongoDBTutorSessionRepository._to_doc(session, version=1)
        ext_db.tutor_sessions.find_one.return_value = payload
        found = await repo.find_by_student_document(student, doc_id)
        assert found is not None
        assert found.objective == "obj"

        ext_db.tutor_sessions.delete_many.return_value = MagicMock(deleted_count=2)
        deleted = await repo.delete_by_document(doc_id)
        assert deleted == 2

    @pytest.mark.asyncio
    async def test_save_concurrency_error(self, ext_db):
        session = TutorSession.start(uuid4(), uuid4())
        session.version = 3
        ext_db.tutor_sessions.replace_one.return_value = MagicMock(matched_count=0)
        repo = MongoDBTutorSessionRepository(database=ext_db)
        with pytest.raises(ConcurrencyError):
            await repo.save(session)


class TestMongoDBQuizRepositoryExtended:
    @pytest.mark.asyncio
    async def test_find_by_document_owner_delete(self, ext_db):
        owner = uuid4()
        doc_id = uuid4()
        quiz = QuizAggregate.create(
            doc_id,
            owner,
            [QuizQuestion(text="P", options={"A": "1", "B": "2"}, correct_answer="A")],
        )
        raw = MongoDBQuizRepository._to_doc(quiz)
        ext_db.quizzes.find.return_value = AsyncCursorMock([raw])
        repo = MongoDBQuizRepository(database=ext_db)
        by_doc = await repo.find_by_document(doc_id)
        assert len(by_doc) == 1

        ext_db.quizzes.find.return_value = AsyncCursorMock([raw])
        by_owner = await repo.find_by_owner(owner)
        assert len(by_owner) == 1

        ext_db.quizzes.delete_many.return_value = MagicMock(deleted_count=1)
        assert await repo.delete_by_document(doc_id) == 1

    @pytest.mark.asyncio
    async def test_find_by_id_none(self, ext_db):
        ext_db.quizzes.find_one.return_value = None
        repo = MongoDBQuizRepository(database=ext_db)
        assert await repo.find_by_id(uuid4()) is None


class TestMongoDBQuizAttemptRepositoryExtended:
    @pytest.mark.asyncio
    async def test_find_by_id_quiz_delete(self, ext_db):
        quiz = QuizAggregate.create(
            uuid4(),
            uuid4(),
            [QuizQuestion(text="P", options={"A": "1", "B": "2"}, correct_answer="A")],
        )
        student = uuid4()
        attempt = QuizAttemptAggregate.create(
            quiz.id, quiz.document_id, student, {0: "A"}, quiz.grade({0: "A"})
        )
        raw = MongoDBQuizAttemptRepository._to_doc(attempt)
        ext_db.quiz_attempts.find_one.return_value = raw
        repo = MongoDBQuizAttemptRepository(database=ext_db)
        found = await repo.find_by_id(attempt.id)
        assert found is not None

        ext_db.quiz_attempts.find.return_value = AsyncCursorMock([raw])
        by_quiz = await repo.find_by_quiz(quiz.id)
        assert len(by_quiz) == 1

        ext_db.quiz_attempts.delete_many.return_value = MagicMock(deleted_count=3)
        assert await repo.delete_by_document(quiz.document_id) == 3


class TestMongoDBTutorInteractionRepositoryExtended:
    @pytest.mark.asyncio
    async def test_find_by_id(self, ext_db):
        from src.domain.aggregates.tutor_interaction import TutorInteractionAggregate

        student = uuid4()
        doc_id = uuid4()
        interaction = TutorInteractionAggregate.create(student, doc_id, "Q", "A")
        raw = {
            "_id": str(interaction.id),
            "student_id": str(student),
            "document_id": str(doc_id),
            "question": "Q",
            "answer": "A",
            "asked_at": interaction.asked_at,
        }
        ext_db.tutor_interactions.find_one.return_value = raw
        repo = MongoDBTutorInteractionRepository(database=ext_db)
        found = await repo.find_by_id(interaction.id)
        assert found is not None
        assert found.answer == "A"

    @pytest.mark.asyncio
    async def test_find_by_student_and_document(self, ext_db):
        from src.domain.aggregates.tutor_interaction import TutorInteractionAggregate

        student = uuid4()
        doc_id = uuid4()
        interaction = TutorInteractionAggregate.create(student, doc_id, "Q", "A")
        raw = MongoDBTutorInteractionRepository._to_doc(interaction)
        ext_db.tutor_interactions.find.return_value = AsyncCursorMock([raw])
        repo = MongoDBTutorInteractionRepository(database=ext_db)
        by_student = await repo.find_by_student(student)
        assert len(by_student) == 1
        by_doc = await repo.find_by_document(doc_id)
        assert len(by_doc) == 1

    @pytest.mark.asyncio
    async def test_save_and_delete_by_document(self, ext_db):
        from src.domain.aggregates.tutor_interaction import TutorInteractionAggregate

        doc_id = uuid4()
        interaction = TutorInteractionAggregate.create(uuid4(), doc_id, "Q", "A")
        ext_db.tutor_interactions.delete_many.return_value = MagicMock(deleted_count=2)
        repo = MongoDBTutorInteractionRepository(database=ext_db)
        await repo.save(interaction)
        ext_db.tutor_interactions.replace_one.assert_awaited_once()
        assert await repo.delete_by_document(doc_id) == 2

    @pytest.mark.asyncio
    async def test_lazy_database(self):
        ext_db = MagicMock()
        ext_db.tutor_interactions.find_one = AsyncMock(return_value=None)
        repo = MongoDBTutorInteractionRepository()
        with patch(
            "src.infrastructure.mongodb.tutor_interaction_repository.get_database",
            AsyncMock(return_value=ext_db),
        ):
            assert await repo.find_by_id(uuid4()) is None
