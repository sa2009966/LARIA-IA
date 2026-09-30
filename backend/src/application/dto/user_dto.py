from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class RegisterUserDTO:
    username: str
    email: str
    password: str


@dataclass
class UserDTO:
    id: UUID
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    email_verified: bool = False
    has_password: bool = True
    auth_provider: str = "password"
