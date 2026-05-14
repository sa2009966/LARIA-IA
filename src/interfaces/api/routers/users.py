from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.services.user_service import UserService
from src.interfaces.api.dependencies import get_current_user_id, get_user_service
from src.interfaces.schemas.user_schemas import UserResponse

router = APIRouter(prefix="/users", tags=["Usuarios"])


def _map(user) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user_id: Annotated[int, Depends(get_current_user_id)],
    service: Annotated[UserService, Depends(get_user_service)],
):
    try:
        user = service.get_by_id(current_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _map(user)


@router.get("/", response_model=list[UserResponse])
def list_users(
    _: Annotated[int, Depends(get_current_user_id)],
    service: Annotated[UserService, Depends(get_user_service)],
):
    return [_map(u) for u in service.list_users()]


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(
    user_id: int,
    _: Annotated[int, Depends(get_current_user_id)],
    service: Annotated[UserService, Depends(get_user_service)],
):
    try:
        service.deactivate_user(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
