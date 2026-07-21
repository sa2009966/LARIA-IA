from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from src.application.dto.user_dto import RegisterUserDTO
from src.application.services.user_service import UserService
from src.infrastructure.config import JWT_ALGORITHM, settings
from src.interfaces.api.openapi_responses import (
    RESP_401_UNAUTHORIZED,
    RESP_409_CONFLICT,
    RESP_422_VALIDATION,
)
from src.interfaces.api.dependencies import get_user_service
from src.interfaces.schemas.user_schemas import TokenResponse, UserRegisterRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def _create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar usuario",
    description=(
        "Crea una cuenta nueva con nombre de usuario, email y contraseña. "
        "No requiere JWT. Las contraseñas deben cumplir la longitud mínima definida en el esquema."
    ),
    response_description="Datos públicos del usuario recién creado (sin contraseña).",
    responses={
        **RESP_409_CONFLICT,
        **RESP_422_VALIDATION,
    },
)
async def register(
    body: UserRegisterRequest,
    service: Annotated[UserService, Depends(get_user_service)],
):
    dto = RegisterUserDTO(
        username=body.username,
        email=body.email,
        password=body.password,
    )
    try:
        user = await service.register(dto)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Obtener token JWT (OAuth2 password)",
    description=(
        "Intercambio de credenciales por un `access_token` JWT. "
        "El campo `username` del formulario debe contener el **email** del usuario "
        "(compatibilidad con `OAuth2PasswordRequestForm`). "
        "Este endpoint no usa cabecera `Authorization`."
    ),
    response_description="Token Bearer para usar en `Authorization: Bearer <access_token>`.",
    responses={
        **RESP_401_UNAUTHORIZED,
        **RESP_422_VALIDATION,
    },
)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: Annotated[UserService, Depends(get_user_service)],
):
    try:
        user = await service.authenticate(form.username, form.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = _create_access_token(str(user.id))
    return TokenResponse(access_token=token)