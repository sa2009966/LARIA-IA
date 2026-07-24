"""Tests de versionado optimista de perfil y fail-fast de producción."""
from uuid import uuid4

import pytest

from src.domain.aggregates.student_profile import StudentProfile
from src.domain.exceptions import ConcurrencyError
from src.infrastructure.config import Settings, validate_runtime_settings
from src.infrastructure.persistence.in_memory_student_profile_repo import (
    InMemoryStudentProfileRepository,
)


@pytest.mark.asyncio
async def test_profile_optimistic_lock_rejects_stale_version():
    repo = InMemoryStudentProfileRepository()
    student = uuid4()
    p1 = StudentProfile.create(student)
    await repo.save(p1)
    assert p1.version == 1

    loaded_a = await repo.find_by_student(student)
    loaded_b = await repo.find_by_student(student)
    assert loaded_a is not None and loaded_b is not None
    loaded_a.record_quiz_result(uuid4(), 1.0)
    await repo.save(loaded_a)
    assert loaded_a.version == 2

    loaded_b.record_quiz_result(uuid4(), 0.0)
    with pytest.raises(ConcurrencyError):
        await repo.save(loaded_b)


def test_production_rejects_memory_db():
    s = Settings(
        SECRET_KEY="x" * 32,
        OPENAI_API_KEY="sk-test",
        APP_ENV="production",
        DB_PROVIDER="memory",
        MONGODB_URL="mongodb://localhost:27017",
    )
    with pytest.raises(RuntimeError, match="mongodb"):
        validate_runtime_settings(s)


def test_production_requires_mongo_url():
    s = Settings(
        SECRET_KEY="x" * 32,
        OPENAI_API_KEY="sk-test",
        APP_ENV="production",
        DB_PROVIDER="mongodb",
        MONGODB_URL="   ",
    )
    with pytest.raises(RuntimeError, match="MONGODB_URL"):
        validate_runtime_settings(s)
