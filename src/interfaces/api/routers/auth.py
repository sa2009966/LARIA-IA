from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt

from src.application.services.user_service import UserService
from src.infrastructure.config import settings
from src.interfaces.api.dependencies import get_user_service
from src.interfaces.schemas.user_schemas import TokenResponse, UserRegisterRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def _create_access_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: UserRegisterRequest,
    service: Annotated[UserService, Depends(get_user_service)],
):
    try:
        user = service.register(body.username, body.email, body.password, body.role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return UserResponse(
        id=user.id,  # type: ignore[arg-type]
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/token", response_model=TokenResponse)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: Annotated[UserService, Depends(get_user_service)],
):
    try:
        user = service.authenticate(form.username, form.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = _create_access_token(user.id)  # type: ignore[arg-type]
    return TokenResponse(access_token=token)
