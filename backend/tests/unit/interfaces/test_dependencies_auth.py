"""Cobertura get_current_user y require_admin."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException

from src.domain.aggregates.user_aggregate import UserAggregate
from src.infrastructure.config import JWT_ALGORITHM, settings
from src.infrastructure.persistence.in_memory_user_repo import InMemoryUserRepository
from src.interfaces.api import dependencies as deps


@pytest.mark.asyncio
async def test_get_current_user_invalid_token(monkeypatch):
    deps.get_user_repo.cache_clear()
    monkeypatch.setattr(deps, "get_user_repo", lambda: InMemoryUserRepository())
    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user("not-a-jwt")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_missing_subject(monkeypatch):
    token = jwt.encode({"foo": "bar"}, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)
    deps.get_user_repo.cache_clear()
    monkeypatch.setattr(deps, "get_user_repo", lambda: InMemoryUserRepository())
    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user(token)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_inactive(monkeypatch):
    repo = InMemoryUserRepository()
    user = UserAggregate.register("inactive", "inactive@example.com", "SecurePass1x")
    user.deactivate()
    await repo.save(user)
    token = jwt.encode({"sub": str(user.id)}, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)
    deps.get_user_repo.cache_clear()
    monkeypatch.setattr(deps, "get_user_repo", lambda: repo)
    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user(token)
    assert exc.value.status_code == 401
    assert "inactivo" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_get_current_user_not_found(monkeypatch):
    token = jwt.encode({"sub": str(uuid4())}, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)
    mock_repo = MagicMock()
    mock_repo.find_by_id = AsyncMock(return_value=None)
    deps.get_user_repo.cache_clear()
    monkeypatch.setattr(deps, "get_user_repo", lambda: mock_repo)
    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user(token)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_require_admin_forbidden():
    user = UserAggregate.register("student", "student@example.com", "SecurePass1x")
    with pytest.raises(HTTPException) as exc:
        await deps.require_admin(user)
    assert exc.value.status_code == 403
