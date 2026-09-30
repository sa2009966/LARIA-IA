from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.services.user_service import UserService
from src.domain.aggregates.user_aggregate import UserAggregate
from src.interfaces.api.openapi_responses import (
    RESP_401_UNAUTHORIZED,
    RESP_403_FORBIDDEN,
    RESP_404_NOT_FOUND,
)
from src.domain.ports.external_identity import ExternalIdentityVerifier, InvalidExternalToken
from src.interfaces.api.dependencies import (
    get_google_verifier,
    get_account_service,
    get_current_user,
    get_user_service,
    require_admin,
)
from src.interfaces.schemas.user_schemas import AccountDeletionRequest, UserResponse

router = APIRouter(prefix="/users", tags=["Usuarios"])


def _map(user) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email.value if hasattr(user.email, "value") else user.email,
        role=user.role.value if hasattr(user.role, "value") else user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        email_verified=getattr(user, "email_verified", False),
        # Agregado (método) o DTO (campo): quien llama no tiene por qué saberlo.
        has_password=(
            user.has_password() if callable(getattr(user, "has_password", None))
            else getattr(user, "has_password", True)
        ),
        auth_provider=(
            "clerk" if getattr(user, "clerk_user_id", None)
            else "google" if getattr(user, "google_sub", None)
            else getattr(user, "auth_provider", "password")
        ),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Perfil del usuario autenticado",
    description=(
        "Devuelve los datos del usuario identificado por el JWT. "
        "Requiere cabecera `Authorization: Bearer <token>` válida."
    ),
    response_description="Perfil completo del usuario actual.",
    responses={
        **RESP_401_UNAUTHORIZED,
    },
)
async def get_me(
    current_user: Annotated[UserAggregate, Depends(get_current_user)],
):
    return _map(current_user)


@router.get(
    "/",
    response_model=list[UserResponse],
    summary="Listar todos los usuarios",
    description="Lista de cuentas registradas. Requiere JWT válido con rol `admin`.",
    response_description="Colección de usuarios (sin contraseñas).",
    responses={
        **RESP_401_UNAUTHORIZED,
        **RESP_403_FORBIDDEN,
    },
)
async def list_users(
    _: Annotated[UserAggregate, Depends(require_admin)],
    service: Annotated[UserService, Depends(get_user_service)],
):
    users = await service.list_users()
    return [_map(u) for u in users]


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar mi cuenta y todos mis datos",
    description=(
        "Borra **definitivamente** la cuenta del usuario autenticado y todo lo suyo: "
        "documentos y sus archivos originales, chats, cuestionarios y nivelaciones, "
        "intentos, interacciones con el tutor, sesiones, rutas de aprendizaje y "
        "perfil de aprendizaje. No se puede deshacer.\n\n"
        "Pide la contraseña actual (`password`) —o, en cuentas de Google, un `google_id_token` "
        "recién emitido para el mismo correo— aunque la petición ya lleve token: "
        "un token robado no debe bastar para destruir una cuenta. Contraseña "
        "incorrecta → **403**. Tras borrarla, el token deja de servir (**401**)."
    ),
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Cuenta y datos borrados."},
        **RESP_401_UNAUTHORIZED,
        **RESP_403_FORBIDDEN,
    },
)
async def delete_my_account(
    body: AccountDeletionRequest,
    current_user: Annotated[UserAggregate, Depends(get_current_user)],
    google: Annotated[ExternalIdentityVerifier, Depends(get_google_verifier)],
    service=Depends(get_account_service),
):
    correo = None
    if body.google_id_token:
        try:
            correo = (await google.verify(body.google_id_token)).email
        except InvalidExternalToken as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    elif not body.password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Confirma con tu contraseña o, si entras con Google, con tu cuenta de Google.",
        )
    try:
        await service.delete_account(current_user.id, body.password, verified_email=correo)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desactivar usuario",
    description=(
        "Marca como inactivo al usuario con el `user_id` indicado. "
        "Requiere JWT con rol `admin`. Respuesta vacía con código 204 si tiene éxito."
    ),
    response_description="Sin cuerpo (operación idempotente desde el punto de vista HTTP).",
    responses={
        status.HTTP_204_NO_CONTENT: {
            "description": "Usuario desactivado correctamente; no se devuelve JSON.",
        },
        **RESP_401_UNAUTHORIZED,
        **RESP_403_FORBIDDEN,
        **RESP_404_NOT_FOUND,
    },
)
async def deactivate_user(
    user_id: UUID,
    _: Annotated[UserAggregate, Depends(require_admin)],
    service: Annotated[UserService, Depends(get_user_service)],
):
    try:
        await service.deactivate_user(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
