from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.document_service import DocumentService
from src.application.dto.document_dto import UploadDocumentDTO, DocumentDTO, DocumentListDTO
from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.ports.repositories import DocumentRepository
from src.domain.ports.event_bus import EventBus
from src.infrastructure.persistence.in_memory_quiz_attempt_repo import InMemoryQuizAttemptRepository
from src.infrastructure.persistence.in_memory_quiz_repo import InMemoryQuizRepository
from src.infrastructure.persistence.in_memory_student_profile_repo import (
    InMemoryStudentProfileRepository,
)
from src.infrastructure.persistence.in_memory_tutor_interaction_repo import (
    InMemoryTutorInteractionRepository,
)
from src.domain.aggregates.quiz_aggregate import QuizAggregate
from src.domain.aggregates.quiz_attempt_aggregate import QuizAttemptAggregate
from src.domain.aggregates.tutor_interaction import TutorInteractionAggregate
from src.domain.value_objects.question import QuizQuestion


@pytest.fixture
def repo_mock() -> AsyncMock:
    mock = AsyncMock(spec=DocumentRepository)
    mock.find_by_id = AsyncMock()
    mock.find_by_owner = AsyncMock(return_value=[])
    mock.save = AsyncMock()
    mock.delete = AsyncMock()
    return mock


@pytest.fixture
def event_bus_mock() -> AsyncMock:
    mock = AsyncMock(spec=EventBus)
    mock.publish = AsyncMock()
    return mock


@pytest.fixture
def servicio(repo_mock: AsyncMock, event_bus_mock: AsyncMock) -> DocumentService:
    return DocumentService(document_repository=repo_mock, event_bus=event_bus_mock)


class TestDocumentService:
    @pytest.mark.asyncio
    async def test_upload_crea_documento_con_owner_id(self, servicio: DocumentService, repo_mock: AsyncMock):
        owner_id = uuid4()
        dto = UploadDocumentDTO(filename="nota.txt", content="texto", subject="Matemática")
        result = await servicio.upload(owner_id, dto)
        assert isinstance(result, DocumentDTO)
        assert result.owner_id == owner_id
        assert result.filename == "nota.txt"
        assert result.subject == "Matemática"
        repo_mock.save.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_id_lanza_si_no_existe(self, servicio: DocumentService, repo_mock: AsyncMock):
        repo_mock.find_by_id.return_value = None
        with pytest.raises(ValueError, match="no encontrado"):
            await servicio.get_by_id(uuid4(), uuid4())

    @pytest.mark.asyncio
    async def test_get_by_id_denegado_si_owner_no_coincide(self, servicio: DocumentService, repo_mock: AsyncMock):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "f.txt", "cuerpo", "Física")
        repo_mock.find_by_id.return_value = doc
        with pytest.raises(PermissionError, match="No tienes permiso"):
            await servicio.get_by_id(doc.id, uuid4())

    @pytest.mark.asyncio
    async def test_list_by_owner_delega_filtro(self, servicio: DocumentService, repo_mock: AsyncMock):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "a.pdf", "x", "Historia")
        repo_mock.find_by_owner.return_value = [doc]
        result = await servicio.list_by_owner(owner_id)
        assert isinstance(result, DocumentListDTO)
        assert result.total == 1

    @pytest.mark.asyncio
    async def test_delete_permite_solo_al_propietario(self, servicio: DocumentService, repo_mock: AsyncMock):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "f.txt", "cuerpo", "Física")
        repo_mock.find_by_id.return_value = doc
        await servicio.delete(doc.id, owner_id)
        repo_mock.delete.assert_awaited_once_with(doc.id)

    @pytest.mark.asyncio
    async def test_delete_denegado_si_otro_usuario(self, servicio: DocumentService, repo_mock: AsyncMock):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "f.txt", "cuerpo", "Física")
        repo_mock.find_by_id.return_value = doc
        with pytest.raises(PermissionError, match="No tienes permiso"):
            await servicio.delete(doc.id, uuid4())
        repo_mock.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_cascada_limpia_evidencia_y_perfil(self, repo_mock: AsyncMock):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "f.txt", "cuerpo", "Física")
        repo_mock.find_by_id.return_value = doc

        quiz_repo = InMemoryQuizRepository()
        attempt_repo = InMemoryQuizAttemptRepository()
        interaction_repo = InMemoryTutorInteractionRepository()
        profile_repo = InMemoryStudentProfileRepository()

        q = QuizQuestion(text="P", options={"A": "1", "B": "2"}, correct_answer="A")
        quiz = QuizAggregate.create(doc.id, owner_id, [q])
        await quiz_repo.save(quiz)
        grade = quiz.grade({0: "A"})
        attempt = QuizAttemptAggregate.create(
            quiz_id=quiz.id,
            document_id=doc.id,
            student_id=owner_id,
            answers={0: "A"},
            grade=grade,
        )
        await attempt_repo.save(attempt)
        await interaction_repo.save(
            TutorInteractionAggregate.create(owner_id, doc.id, "¿?", "r")
        )
        profile = StudentProfile.create(owner_id)
        profile.record_quiz_result(doc.id, 1.0)
        await profile_repo.save(profile)

        service = DocumentService(
            document_repository=repo_mock,
            quiz_repository=quiz_repo,
            attempt_repository=attempt_repo,
            interaction_repository=interaction_repo,
            profile_repository=profile_repo,
        )
        await service.delete(doc.id, owner_id)

        assert await quiz_repo.find_by_document(doc.id) == []
        assert await attempt_repo.find_by_student(owner_id) == []
        assert await interaction_repo.find_by_document(doc.id) == []
        cleared = await profile_repo.find_by_student(owner_id)
        assert cleared is not None
        assert cleared.mastery_for(doc.id) == 0.0
        assert doc.id not in cleared.mastery_by_document
