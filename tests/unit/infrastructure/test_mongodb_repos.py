import pytest
from unittest.mock import AsyncMock, MagicMock


class AsyncCursorMock:
    def __init__(self, items):
        self._items = items

    def __aiter__(self):
        return self._async_gen()

    async def _async_gen(self):
        for item in self._items:
            yield item
from uuid import uuid4

from src.domain.aggregates.user_aggregate import UserAggregate
from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.aggregates.analysis_aggregate import AnalysisAggregate
from src.domain.value_objects.analysis_result import AnalysisResult
from src.domain.value_objects.question import Quiz, QuizQuestion
from src.domain.value_objects.email import Email
from src.infrastructure.mongodb.user_repository import MongoDBUserRepository
from src.infrastructure.mongodb.document_repository import MongoDBDocumentRepository
from src.infrastructure.mongodb.analysis_repository import MongoDBAnalysisRepository


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.users = MagicMock()
    db.users.find_one = AsyncMock()
    db.users.find = MagicMock()
    db.users.replace_one = AsyncMock()
    db.users.delete_one = AsyncMock()
    db.documents = MagicMock()
    db.documents.find_one = AsyncMock()
    db.documents.find = MagicMock()
    db.documents.replace_one = AsyncMock()
    db.documents.delete_one = AsyncMock()
    db.analyses = MagicMock()
    db.analyses.find_one = AsyncMock()
    db.analyses.replace_one = AsyncMock()
    return db


class TestMongoDBUserRepository:

    @pytest.mark.asyncio
    async def test_save_and_find_by_id(self, mock_db):
        repo = MongoDBUserRepository(database=mock_db)
        user = UserAggregate.register("ana", "ana@example.com", "SecurePass1")

        await repo.save(user)
        mock_db.users.replace_one.assert_awaited_once()

        mock_db.users.find_one.return_value = {
            "_id": str(user.id),
            "username": "ana",
            "email": "ana@example.com",
            "hashed_password": user.hashed_password,
            "role": "student",
            "is_active": True,
            "created_at": user.created_at,
        }
        found = await repo.find_by_id(user.id)
        assert found is not None
        assert found.username == "ana"
        assert found.email.value == "ana@example.com"

    @pytest.mark.asyncio
    async def test_find_by_email(self, mock_db):
        repo = MongoDBUserRepository(database=mock_db)
        user = UserAggregate.register("luis", "luis@example.com", "SecurePass1")
        mock_db.users.find_one.return_value = {
            "_id": str(user.id),
            "username": "luis",
            "email": "luis@example.com",
            "hashed_password": user.hashed_password,
            "role": "student",
            "is_active": True,
            "created_at": user.created_at,
        }
        found = await repo.find_by_email(Email("luis@example.com"))
        assert found is not None
        assert found.username == "luis"

    @pytest.mark.asyncio
    async def test_find_by_username(self, mock_db):
        repo = MongoDBUserRepository(database=mock_db)
        user = UserAggregate.register("pedro", "pedro@example.com", "SecurePass1")
        mock_db.users.find_one.return_value = {
            "_id": str(user.id),
            "username": "pedro",
            "email": "pedro@example.com",
            "hashed_password": user.hashed_password,
            "role": "student",
            "is_active": True,
            "created_at": user.created_at,
        }
        found = await repo.find_by_username("pedro")
        assert found is not None
        assert found.email.value == "pedro@example.com"

    @pytest.mark.asyncio
    async def test_find_by_id_returns_none(self, mock_db):
        repo = MongoDBUserRepository(database=mock_db)
        mock_db.users.find_one.return_value = None
        found = await repo.find_by_id(uuid4())
        assert found is None

    @pytest.mark.asyncio
    async def test_delete(self, mock_db):
        repo = MongoDBUserRepository(database=mock_db)
        user_id = uuid4()
        await repo.delete(user_id)
        mock_db.users.delete_one.assert_awaited_once_with({"_id": str(user_id)})

    @pytest.mark.asyncio
    async def test_list_all(self, mock_db):
        repo = MongoDBUserRepository(database=mock_db)
        u1 = UserAggregate.register("a", "a@example.com", "SecurePass1")
        u2 = UserAggregate.register("b", "b@example.com", "SecurePass2")

        mock_db.users.find.return_value = AsyncCursorMock([
            {
                "_id": str(u1.id),
                "username": u1.username,
                "email": u1.email.value,
                "hashed_password": u1.hashed_password,
                "role": "student",
                "is_active": True,
                "created_at": u1.created_at,
            },
            {
                "_id": str(u2.id),
                "username": u2.username,
                "email": u2.email.value,
                "hashed_password": u2.hashed_password,
                "role": "student",
                "is_active": True,
                "created_at": u2.created_at,
            },
        ])

        users = await repo.list_all()
        assert len(users) == 2


class TestMongoDBDocumentRepository:

    @pytest.mark.asyncio
    async def test_save_and_find_by_id(self, mock_db):
        repo = MongoDBDocumentRepository(database=mock_db)
        doc = DocumentAggregate.upload(uuid4(), "test.txt", "content", "Historia")

        await repo.save(doc)
        mock_db.documents.replace_one.assert_awaited_once()

        mock_db.documents.find_one.return_value = {
            "_id": str(doc.id),
            "owner_id": str(doc.owner_id),
            "filename": "test.txt",
            "content": "content",
            "subject": "Historia",
            "status": "uploaded",
            "uploaded_at": doc.uploaded_at,
            "error_message": None,
        }
        found = await repo.find_by_id(doc.id)
        assert found is not None
        assert found.filename == "test.txt"
        assert found.subject.value == "Historia"

    @pytest.mark.asyncio
    async def test_find_by_owner(self, mock_db):
        repo = MongoDBDocumentRepository(database=mock_db)
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "doc.txt", "x", "Matemática")

        mock_db.documents.find.return_value = AsyncCursorMock([
            {
                "_id": str(doc.id),
                "owner_id": str(owner_id),
                "filename": "doc.txt",
                "content": "x",
                "subject": "Matemática",
                "status": "uploaded",
                "uploaded_at": doc.uploaded_at,
                "error_message": None,
            },
        ])

        docs = await repo.find_by_owner(owner_id)
        assert len(docs) == 1

    @pytest.mark.asyncio
    async def test_save_with_analysis_result(self, mock_db):
        repo = MongoDBDocumentRepository(database=mock_db)
        doc = DocumentAggregate.upload(uuid4(), "f.txt", "c", "Ciencias")
        result = AnalysisResult(summary="Resumen.", confidence_score=0.9)
        doc.complete_analysis(result)
        doc.clear_events()

        await repo.save(doc)
        call_args = mock_db.documents.replace_one.call_args[0][1]
        assert "analysis_result" in call_args
        assert call_args["analysis_result"]["summary"] == "Resumen."

    @pytest.mark.asyncio
    async def test_find_with_analysis_result(self, mock_db):
        repo = MongoDBDocumentRepository(database=mock_db)
        doc_id = uuid4()
        mock_db.documents.find_one.return_value = {
            "_id": str(doc_id),
            "owner_id": str(uuid4()),
            "filename": "f.txt",
            "content": "c",
            "subject": "Biología",
            "status": "analyzed",
            "uploaded_at": None,
            "error_message": None,
            "analysis_result": {
                "summary": "Resumen.",
                "key_concepts": [],
                "suggested_questions": [],
                "confidence_score": 0.9,
            },
        }
        found = await repo.find_by_id(doc_id)
        assert found is not None
        assert found.has_analysis()
        assert found.analysis_result.summary == "Resumen."


class TestMongoDBAnalysisRepository:

    @pytest.mark.asyncio
    async def test_save_and_find_by_document(self, mock_db):
        repo = MongoDBAnalysisRepository(database=mock_db)
        doc_id = uuid4()
        result = AnalysisResult(summary="Análisis completo.", confidence_score=0.95)
        analysis = AnalysisAggregate.create(doc_id, result, model_used="gpt-4o-mini")

        await repo.save(analysis)
        mock_db.analyses.replace_one.assert_awaited_once()

        mock_db.analyses.find_one.return_value = {
            "_id": str(analysis.id),
            "document_id": str(doc_id),
            "model_used": "gpt-4o-mini",
            "created_at": analysis.created_at,
            "result": {
                "summary": "Análisis completo.",
                "key_concepts": [],
                "suggested_questions": [],
                "confidence_score": 0.95,
            },
        }
        found = await repo.find_by_document(doc_id)
        assert found is not None
        assert found.result is not None
        assert found.result.summary == "Análisis completo."

    @pytest.mark.asyncio
    async def test_save_with_quiz(self, mock_db):
        repo = MongoDBAnalysisRepository(database=mock_db)
        doc_id = uuid4()
        result = AnalysisResult(summary="S", confidence_score=0.8)
        analysis = AnalysisAggregate.create(doc_id, result)
        quiz = Quiz(questions=[
            QuizQuestion(text="P1", options={"A": "1", "B": "2"}, correct_answer="A"),
        ])
        analysis.add_quiz(quiz)

        await repo.save(analysis)
        call_args = mock_db.analyses.replace_one.call_args[0][1]
        assert "quiz" in call_args
        assert len(call_args["quiz"]["questions"]) == 1