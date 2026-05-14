from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator


class UserRegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str = "student"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in {"student", "teacher", "admin"}:
            raise ValueError("El rol debe ser 'student', 'teacher' o 'admin'.")
        return v


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
