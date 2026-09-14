"""Integración Mongo repos con mongomock-motor (find/find_one y filtros reales)."""
from __future__ import annotations

from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

import pytest
from bson import ObjectId
from mongomock_motor import AsyncMongoMockClient

from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.aggregates.quiz_aggregate import QuizAggregate
from src.domain.aggregates.quiz_attempt_aggregate import QuizAttemptAggregate
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.aggregates.tutor_session import TutorSession
from src.domain.aggregates.user_aggregate import UserAggregate
from src.domain.value_objects.email import Email
from src.domain.value_objects.question import QuizQuestion
from src.infrastructure.mongodb.document_repository import MongoDBDocumentRepository
from src.infrastructure.mongodb.gridfs_document_blob_store import GridFSDocumentBlobStore
from src.infrastructure.mongodb.quiz_attempt_repository import MongoDBQuizAttemptRepository
from src.infrastructure.mongodb.quiz_repository import MongoDBQuizRepository
from src.infrastructure.mongodb.student_profile_repository import MongoDBStudentProfileRepository
from src.infrastructure.mongodb.tutor_session_repository import MongoDBTutorSessionRepository
from src.infrastructure.mongodb.user_repository import MongoDBUserRepository

from tests.unit.infrastructure.mongomock_gridfs_bucket import MongomockAsyncGridFSBucket


@pytest.fixture
async def mock_db():
    client = AsyncMongoMockClient()
    db = client["laria_test"]
    yield db
    await client.drop_database("laria_test")


class TestUserRepositoryMongomock:
    @pytest.mark.asyncio
    async def test_find_by_email_filter(self, mock_db):
        repo = MongoDBUserRepository(database=mock_db)
        user = UserAggregate.register("ana", "ana@example.com", "SecurePass1x")
        await repo.save(user)

        by_email = await repo.find_by_email(Email("ana@example.com"))
        assert by_email is not None
        assert by_email.username == "ana"

        missing = await repo.find_by_email(Email("other@example.com"))
        assert missing is None

        raw = await mock_db.users.find_one({"email": "ana@example.com"})
        assert raw is not None
        assert raw["_id"] == str(user.id)


class TestDocumentRepositoryMongomock:
    @pytest.mark.asyncio
    async def test_find_by_owner_filter(self, mock_db):
        owner_a = uuid4()
        owner_b = uuid4()
        repo = MongoDBDocumentRepository(database=mock_db)
        doc_a = DocumentAggregate.upload(owner_a, "a.txt", "content-a", "Historia")
        doc_b = DocumentAggregate.upload(owner_b, "b.txt", "content-b", "Ciencias")
        await repo.save(doc_a)
        await repo.save(doc_b)

        docs_a = await repo.find_by_owner(owner_a)
        assert len(docs_a) == 1
        assert docs_a[0].filename == "a.txt"

        cursor_docs = [d async for d in mock_db.documents.find({"owner_id": str(owner_a)})]
        assert len(cursor_docs) == 1
        assert cursor_docs[0]["filename"] == "a.txt"


class TestQuizRepositoryMongomock:
    @pytest.mark.asyncio
    async def test_find_by_document_and_owner_filters(self, mock_db):
        owner = uuid4()
        doc_id = uuid4()
        other_doc = uuid4()
        repo = MongoDBQuizRepository(database=mock_db)
        quiz = QuizAggregate.create(
            doc_id,
            owner,
            [QuizQuestion(text="P?", options={"A": "1", "B": "2"}, correct_answer="A")],
        )
        other = QuizAggregate.create(
            other_doc,
            owner,
            [QuizQuestion(text="Q?", options={"A": "x", "B": "y"}, correct_answer="B")],
        )
        await repo.save(quiz)
        await repo.save(other)

        by_doc = await repo.find_by_document(doc_id)
        assert len(by_doc) == 1
        assert by_doc[0].id == quiz.id

        by_owner = await repo.find_by_owner(owner)
        assert len(by_owner) == 2

        raw_doc = await mock_db.quizzes.find_one({"document_id": str(doc_id)})
        assert raw_doc is not None
        raw_owner = [q async for q in mock_db.quizzes.find({"owner_id": str(owner)})]
        assert len(raw_owner) == 2


class TestQuizAttemptRepositoryMongomock:
    @pytest.mark.asyncio
    async def test_find_by_quiz_and_student_filters(self, mock_db):
        repo = MongoDBQuizAttemptRepository(database=mock_db)
        quiz_id = uuid4()
        doc_id = uuid4()
        student_a = uuid4()
        student_b = uuid4()
        quiz = QuizAggregate.create(
            doc_id,
            uuid4(),
            [QuizQuestion(text="P", options={"A": "1", "B": "2"}, correct_answer="A")],
        )
        grade = quiz.grade({0: "A"})
        attempt_a = QuizAttemptAggregate.create(quiz_id, doc_id, student_a, {0: "A"}, grade)
        attempt_b = QuizAttemptAggregate.create(quiz_id, doc_id, student_b, {0: "B"}, grade)
        await repo.save(attempt_a)
        await repo.save(attempt_b)

        by_quiz = await repo.find_by_quiz(quiz_id)
        assert len(by_quiz) == 2

        by_student = await repo.find_by_student(student_a)
        assert len(by_student) == 1
        assert by_student[0].student_id == student_a

        raw_quiz = [a async for a in mock_db.quiz_attempts.find({"quiz_id": str(quiz_id)})]
        assert len(raw_quiz) == 2
        raw_student = await mock_db.quiz_attempts.find_one({"student_id": str(student_a)})
        assert raw_student is not None

    @pytest.mark.asyncio
    async def test_delete_by_document_filter(self, mock_db):
        repo = MongoDBQuizAttemptRepository(database=mock_db)
        doc_id = uuid4()
        attempt = QuizAttemptAggregate.create(
            uuid4(),
            doc_id,
            uuid4(),
            {0: "A"},
            QuizAggregate.create(
                doc_id,
                uuid4(),
                [QuizQuestion(text="P", options={"A": "1", "B": "2"}, correct_answer="A")],
            ).grade({0: "A"}),
        )
        await repo.save(attempt)
        deleted = await repo.delete_by_document(doc_id)
        assert deleted == 1
        remaining = [a async for a in mock_db.quiz_attempts.find({"document_id": str(doc_id)})]
        assert remaining == []


class TestStudentProfileRepositoryMongomock:
    @pytest.mark.asyncio
    async def test_find_by_student_and_version(self, mock_db):
        student = uuid4()
        repo = MongoDBStudentProfileRepository(database=mock_db)
        profile = StudentProfile.create(student)
        await repo.save(profile)
        assert profile.version == 1

        found = await repo.find_by_student(student)
        assert found is not None
        assert found.student_id == student

        raw = await mock_db.student_profiles.find_one({"_id": str(student)})
        assert raw is not None
        assert raw["version"] == 1

        profile.record_quiz_result(uuid4(), 0.75)
        await repo.save(profile)
        assert profile.version == 2
        updated = await mock_db.student_profiles.find_one(
            {"_id": str(student)},
            projection={"version": 1},
        )
        assert updated["version"] == 2


class TestTutorSessionRepositoryMongomock:
    @pytest.mark.asyncio
    async def test_find_by_student_document_and_delete_by_document(self, mock_db):
        student = uuid4()
        doc_id = uuid4()
        other_doc = uuid4()
        repo = MongoDBTutorSessionRepository(database=mock_db)
        session = TutorSession.start(student, doc_id, objective="obj")
        other = TutorSession.start(student, other_doc, objective="other")
        await repo.save(session)
        await repo.save(other)

        found = await repo.find_by_student_document(student, doc_id)
        assert found is not None
        assert found.objective == "obj"

        composite_id = f"{student}:{doc_id}"
        raw = await mock_db.tutor_sessions.find_one({"_id": composite_id})
        assert raw is not None
        assert raw["student_id"] == str(student)
        assert raw["document_id"] == str(doc_id)

        deleted = await repo.delete_by_document(doc_id)
        assert deleted == 1
        remaining = [s async for s in mock_db.tutor_sessions.find({"document_id": str(doc_id)})]
        assert remaining == []


class TestGridFSMongomock:
    @pytest.mark.asyncio
    async def test_put_get_delete_via_mongomock_collections(self, mock_db):
        store = GridFSDocumentBlobStore(database=mock_db)
        bucket = MongomockAsyncGridFSBucket(mock_db)
        with patch.object(store, "_bucket", return_value=bucket):
            blob_id = await store.put(b"gridfs-payload", filename="doc.txt")
            data = await store.get(blob_id)
            assert data == b"gridfs-payload"

            file_doc = await mock_db["fs.files"].find_one({"_id": ObjectId(blob_id)})
            assert file_doc is not None
            chunk_doc = await mock_db["fs.chunks"].find_one({"files_id": file_doc["_id"]})
            assert chunk_doc is not None

            await store.delete(blob_id)
            assert await mock_db["fs.files"].find_one({"_id": file_doc["_id"]}) is None

    @pytest.mark.asyncio
    async def test_gridfs_upload_from_stream_roundtrip(self, mock_db):
        bucket = MongomockAsyncGridFSBucket(mock_db)
        file_id = await bucket.upload_from_stream("f.txt", BytesIO(b"hello-mock"))
        buf = BytesIO()
        await bucket.download_to_stream(file_id, buf)
        assert buf.getvalue() == b"hello-mock"
