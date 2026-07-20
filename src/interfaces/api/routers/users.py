from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.services.user_service import UserService
from src.interfaces.api.openapi_responses import (
    RESP_401_UNAUTHORIZED,
    RESP_404_NOT_FOUND,
)
from src.interfaces.api.dependencies import get_current_user_id, get_user_service
from src.interfaces.schemas.user_schemas import UserResponse

router = APIRouter(prefix="/users", tags=["Usuarios"])


def _map(user) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
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
        **RESP_404_NOT_FOUND,
    },
)
async def get_me(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[UserService, Depends(get_user_service)],
):
    from uuid import UUID
    try:
        user = await service.get_by_id(UUID(current_user_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _map(user)


@router.get(
    "/",
    response_model=list[UserResponse],
    summary="Listar todos los usuarios",
    description=(
        "Lista de cuentas registradas. Requiere JWT válido. "
        "(La política de autorización por roles puede reforzarse en futuras versiones.)"
    ),
    response_description="Colección de usuarios (sin contraseñas).",
    responses={
        **RESP_401_UNAUTHORIZED,
    },
)
async def list_users(
    _: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[UserService, Depends(get_user_service)],
):
    users = await service.list_users()
    return [_map(u) for u in users]


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desactivar usuario",
    description=(
        "Marca como inactivo al usuario con el `user_id` indicado. "
        "Requiere JWT. Respuesta vacía con código 204 si tiene éxito."
    ),
    response_description="Sin cuerpo (operación idempotente desde el punto de vista HTTP).",
    responses={
        status.HTTP_204_NO_CONTENT: {
            "description": "Usuario desactivado correctamente; no se devuelve JSON.",
        },
        **RESP_401_UNAUTHORIZED,
        **RESP_404_NOT_FOUND,
    },
)
async def deactivate_user(
    user_id: str,
    _: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[UserService, Depends(get_user_service)],
):
    try:
        await service.deactivate_user(UUID(user_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))