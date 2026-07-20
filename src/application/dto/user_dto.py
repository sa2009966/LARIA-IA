from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class RegisterUserDTO:
    username: str
    email: str
    password: str
    role: str = "student"


@dataclass
class UserDTO:
    id: UUID
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
