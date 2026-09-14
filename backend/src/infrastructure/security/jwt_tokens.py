"""Emisión de JWT de acceso (fuera de routers)."""
from datetime import datetime, timedelta, timezone

import jwt

from src.infrastructure.config import JWT_ALGORITHM, settings


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)
