from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    username: Annotated[str, Field(min_length=2, max_length=64, description="Nombre de usuario visible")]
    email: EmailStr
    password: Annotated[
        str,
        Field(
            min_length=12,
            max_length=256,
            description="Mínimo 12 caracteres, mayúsculas, minúsculas y dígito",
        ),
    ]

    @field_validator("username")
    @classmethod
    def username_sin_espacios_extremos(cls, v: str) -> str:
        s = v.strip()
        if len(s) < 2:
            raise ValueError("El nombre de usuario debe tener al menos 2 caracteres visibles.")
        return s


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    username: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
