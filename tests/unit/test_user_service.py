"""Pruebas unitarias de `UserService`.

Se usa `unittest.mock.MagicMock` como sustituto del puerto `UserRepository`:
no hay SQLAlchemy, ni MySQL, ni archivos `.env`. El repositorio simplemente
devuelve lo que configuramos en cada prueba (`return_value` / `side_effect`).

Además se sustituye `passlib` en el módulo del servicio mediante `monkeypatch`:
así las pruebas no dependen del backend real de bcrypt (versiones del paquete
`bcrypt`, límites de 72 bytes, etc.) y siguen siendo puramente unitarias.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

import src.application.services.user_service as user_service_module
from src.application.services.user_service import UserService
from src.domain.entities.user import User


def _usuario_guardado(
    *,
    user_id: int = 1,
    username: str = "ana",
    email: str = "ana@example.com",
    role: str = "student",
    is_active: bool = True,
    hashed_password: str = "hash_simulado_en_bd",
) -> User:
    """Entidad de dominio lista para devolverla desde el mock del repositorio."""
    return User(
        id=user_id,
        username=username,
        email=email,
        hashed_password=hashed_password,
        role=role,
        is_active=is_active,
        created_at=datetime.now(UTC),
    )


@pytest.fixture(autouse=True)
def pwd_context_mock(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock del `CryptContext` del servicio: simula `hash` y `verify` sin criptografía real."""
    mock_ctx = MagicMock()
    mock_ctx.hash.return_value = "HASH_MOCK"
    mock_ctx.verify.return_value = False
    monkeypatch.setattr(user_service_module, "_pwd_context", mock_ctx)
    return mock_ctx


@pytest.fixture
def repo_mock() -> MagicMock:
    """Mock del puerto de persistencia: sustituye toda la capa de infraestructura."""
    return MagicMock()


@pytest.fixture
def servicio(repo_mock: MagicMock) -> UserService:
    """Servicio bajo prueba con el repositorio inyectado (mock)."""
    return UserService(repo_mock)


def test_registro_exitoso_persiste_rol_student_por_defecto(
    servicio: UserService,
    repo_mock: MagicMock,
    pwd_context_mock: MagicMock,
) -> None:
    """Si no hay duplicados, se guarda un usuario con rol por defecto `student`."""
    # Simulamos que no existe ningún usuario con ese email ni username.
    repo_mock.find_by_email.return_value = None
    repo_mock.find_by_username.return_value = None
    guardado = _usuario_guardado(role="student", hashed_password="HASH_MOCK")
    repo_mock.save.return_value = guardado

    resultado = servicio.register("ana", "ana@example.com", "clave123")

    assert resultado.role == "student"
    pwd_context_mock.hash.assert_called_once_with("clave123")
    repo_mock.save.assert_called_once()
    # El objeto pasado a `save` es el que construye el servicio: comprobamos rol y email.
    llamado = repo_mock.save.call_args[0][0]
    assert llamado.role == "student"
    assert llamado.email == "ana@example.com"
    assert llamado.hashed_password == "HASH_MOCK"


@pytest.mark.parametrize("rol", ["teacher", "admin"])
def test_registro_exitoso_respeta_rol_recibido(
    servicio: UserService,
    repo_mock: MagicMock,
    rol: str,
) -> None:
    """La capa de aplicación propaga el rol hacia el agregado (validación estricta vive en la API/schema)."""
    repo_mock.find_by_email.return_value = None
    repo_mock.find_by_username.return_value = None
    repo_mock.save.return_value = _usuario_guardado(role=rol)

    servicio.register("luis", "luis@example.com", "otraClave", role=rol)

    creado = repo_mock.save.call_args[0][0]
    assert creado.role == rol


def test_registro_falla_si_email_duplicado(servicio: UserService, repo_mock: MagicMock) -> None:
    """El repositorio simula un email ya ocupado: el servicio debe lanzar `ValueError`."""
    repo_mock.find_by_email.return_value = _usuario_guardado(email="dup@example.com")

    with pytest.raises(ValueError, match="Ya existe un usuario con email"):
        servicio.register("nuevo", "dup@example.com", "x")

    repo_mock.save.assert_not_called()


def test_registro_falla_si_username_duplicado(servicio: UserService, repo_mock: MagicMock) -> None:
    """Email libre pero username ocupado: misma política de conflicto."""
    repo_mock.find_by_email.return_value = None
    repo_mock.find_by_username.return_value = _usuario_guardado(username="existente")

    with pytest.raises(ValueError, match="Ya existe un usuario con username"):
        servicio.register("existente", "nuevo@example.com", "x")

    repo_mock.save.assert_not_called()


def test_autenticacion_exitosa(
    servicio: UserService,
    repo_mock: MagicMock,
    pwd_context_mock: MagicMock,
) -> None:
    """El mock del repo devuelve un usuario; el mock de `verify` confirma la contraseña."""
    pwd_context_mock.verify.return_value = True
    usuario = User(
        id=2,
        username="bea",
        email="bea@example.com",
        hashed_password="cualquier_hash_en_bd",
        role="student",
        is_active=True,
        created_at=datetime.now(UTC),
    )
    repo_mock.find_by_email.return_value = usuario

    autenticado = servicio.authenticate("bea@example.com", "miPass")

    assert autenticado.id == 2
    pwd_context_mock.verify.assert_called_once_with("miPass", "cualquier_hash_en_bd")
    repo_mock.find_by_email.assert_called_once_with("bea@example.com")


def test_autenticacion_falla_credenciales_invalidas(servicio: UserService, repo_mock: MagicMock) -> None:
    """Usuario inexistente o contraseña incorrecta: mismo mensaje genérico."""
    repo_mock.find_by_email.return_value = None

    with pytest.raises(ValueError, match="Credenciales inválidas"):
        servicio.authenticate("no@example.com", "cualquiera")


def test_autenticacion_falla_usuario_inactivo(
    servicio: UserService,
    repo_mock: MagicMock,
    pwd_context_mock: MagicMock,
) -> None:
    """Aunque la contraseña sea correcta, `is_active=False` bloquea el acceso."""
    pwd_context_mock.verify.return_value = True
    u = _usuario_guardado(is_active=False)
    repo_mock.find_by_email.return_value = u

    with pytest.raises(ValueError, match="Usuario inactivo"):
        servicio.authenticate(u.email, "ok")


def test_get_by_id_no_encontrado(servicio: UserService, repo_mock: MagicMock) -> None:
    repo_mock.find_by_id.return_value = None

    with pytest.raises(ValueError, match="no encontrado"):
        servicio.get_by_id(99)


def test_list_users_delega_en_repositorio(servicio: UserService, repo_mock: MagicMock) -> None:
    lista = [_usuario_guardado(user_id=i) for i in range(1, 4)]
    repo_mock.list_all.return_value = lista

    assert servicio.list_users() == lista


def test_deactivate_marca_inactivo_y_guarda(servicio: UserService, repo_mock: MagicMock) -> None:
    activo = _usuario_guardado(is_active=True)
    repo_mock.find_by_id.return_value = activo
    repo_mock.save.side_effect = lambda u: u

    resultado = servicio.deactivate_user(1)

    assert resultado.is_active is False
    repo_mock.save.assert_called_once()
