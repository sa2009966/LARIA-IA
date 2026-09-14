import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

from src.application.services.user_service import UserService
from src.application.dto.user_dto import RegisterUserDTO, UserDTO
from src.domain.aggregates.user_aggregate import UserAggregate
from src.domain.ports.repositories import UserRepository
from src.domain.ports.event_bus import EventBus


@pytest.fixture
def repo_mock() -> AsyncMock:
    mock = AsyncMock(spec=UserRepository)
    mock.find_by_email = AsyncMock(return_value=None)
    mock.find_by_username = AsyncMock(return_value=None)
    mock.save = AsyncMock()
    mock.find_by_id = AsyncMock()
    mock.list_all = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def event_bus_mock() -> AsyncMock:
    mock = AsyncMock(spec=EventBus)
    mock.publish = AsyncMock()
    return mock


@pytest.fixture
def servicio(repo_mock: AsyncMock, event_bus_mock: AsyncMock) -> UserService:
    return UserService(user_repository=repo_mock, event_bus=event_bus_mock)


class TestUserService:
    @pytest.mark.asyncio
    async def test_registro_exitoso(self, servicio: UserService, repo_mock: AsyncMock, event_bus_mock: AsyncMock):
        dto = RegisterUserDTO(username="ana", email="ana@example.com", password="SecurePass1x")
        result = await servicio.register(dto)
        assert isinstance(result, UserDTO)
        assert result.username == "ana"
        assert result.email == "ana@example.com"
        assert result.is_active is True
        repo_mock.save.assert_awaited_once()
        event_bus_mock.publish.assert_awaited()

    @pytest.mark.asyncio
    async def test_registro_falla_si_email_duplicado(self, servicio: UserService, repo_mock: AsyncMock):
        existing = UserAggregate.register("otro", "ana@example.com", "SecurePass1x")
        repo_mock.find_by_email.return_value = existing
        dto = RegisterUserDTO(username="ana", email="ana@example.com", password="SecurePass1x")
        with pytest.raises(ValueError, match="Ya existe un usuario"):
            await servicio.register(dto)
        repo_mock.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_registro_falla_si_username_duplicado(self, servicio: UserService, repo_mock: AsyncMock):
        existing = UserAggregate.register("ana", "otro@example.com", "SecurePass1x")
        repo_mock.find_by_username.return_value = existing
        dto = RegisterUserDTO(username="ana", email="ana@example.com", password="SecurePass1x")
        with pytest.raises(ValueError, match="Ya existe un usuario"):
            await servicio.register(dto)
        repo_mock.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_autenticacion_exitosa(self, servicio: UserService, repo_mock: AsyncMock):
        user = UserAggregate.register("ana", "ana@example.com", "SecurePass1x")
        repo_mock.find_by_email.return_value = user
        result = await servicio.authenticate("ana@example.com", "SecurePass1x")
        assert result.email == "ana@example.com"
        assert result.is_active is True

    @pytest.mark.asyncio
    async def test_autenticacion_falla_credenciales(self, servicio: UserService, repo_mock: AsyncMock):
        user = UserAggregate.register("ana", "ana@example.com", "SecurePass1x")
        repo_mock.find_by_email.return_value = user
        with pytest.raises(ValueError, match="Credenciales invalidas"):
            await servicio.authenticate("ana@example.com", "wrongpass")

    @pytest.mark.asyncio
    async def test_autenticacion_falla_usuario_inexistente(self, servicio: UserService, repo_mock: AsyncMock):
        repo_mock.find_by_email.return_value = None
        with pytest.raises(ValueError, match="Credenciales invalidas"):
            await servicio.authenticate("no@example.com", "pass")

    @pytest.mark.asyncio
    async def test_autenticacion_falla_usuario_inactivo(self, servicio: UserService, repo_mock: AsyncMock):
        user = UserAggregate.register("ana", "ana@example.com", "SecurePass1x")
        user.deactivate()
        repo_mock.find_by_email.return_value = user
        with pytest.raises(ValueError, match="Usuario inactivo"):
            await servicio.authenticate("ana@example.com", "SecurePass1x")

    @pytest.mark.asyncio
    async def test_get_by_id(self, servicio: UserService, repo_mock: AsyncMock):
        user = UserAggregate.register("ana", "ana@example.com", "SecurePass1x")
        repo_mock.find_by_id.return_value = user
        result = await servicio.get_by_id(user.id)
        assert result.id == user.id

    @pytest.mark.asyncio
    async def test_get_by_id_no_encontrado(self, servicio: UserService, repo_mock: AsyncMock):
        repo_mock.find_by_id.return_value = None
        with pytest.raises(ValueError, match="no encontrado"):
            await servicio.get_by_id(uuid4())

    @pytest.mark.asyncio
    async def test_list_users(self, servicio: UserService, repo_mock: AsyncMock):
        u1 = UserAggregate.register("ana", "ana@example.com", "SecurePass1x")
        u2 = UserAggregate.register("luis", "luis@example.com", "SecurePass2x")
        repo_mock.list_all.return_value = [u1, u2]
        result = await servicio.list_users()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_deactivate_marca_inactivo_y_guarda(self, servicio: UserService, repo_mock: AsyncMock):
        user = UserAggregate.register("ana", "ana@example.com", "SecurePass1x")
        repo_mock.find_by_id.return_value = user
        await servicio.deactivate_user(user.id)
        assert user.is_active is False
        repo_mock.save.assert_awaited_once()
