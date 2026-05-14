from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    """Entrada de registro: `EmailStr` valida formato RFC; contraseña con longitud mínima."""

    username: Annotated[str, Field(min_length=2, max_length=64, description="Nombre de usuario visible")]
    email: EmailStr
    password: Annotated[str, Field(min_length=8, max_length=256, description="Contraseña en texto plano (solo tránsito HTTPS)")]
    role: str = "student"

    @field_validator("username")
    @classmethod
    def username_sin_espacios_extremos(cls, v: str) -> str:
        s = v.strip()
        if len(s) < 2:
            raise ValueError("El nombre de usuario debe tener al menos 2 caracteres visibles.")
        return s

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in {"student", "teacher", "admin"}:
            raise ValueError("El rol debe ser 'student', 'teacher' o 'admin'.")
        return v


class UserLoginRequest(BaseModel):
    """Cuerpo JSON opcional para login fuera del formulario OAuth2."""

    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=256, description="No vacío")]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Salida de usuario: email tipado como `EmailStr` para validar formato en respuestas."""

    id: int
    username: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
