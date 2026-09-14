"""Benchmarks de rendimiento QA Fase 5 (medición real, sin Docker)."""
from __future__ import annotations

import statistics
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from src.domain.aggregates.user_aggregate import UserAggregate
from src.domain.value_objects.email import Email
from src.infrastructure.mongodb.user_repository import MongoDBUserRepository
from src.main import app
from tests.conftest import clear_dependency_caches

ITERATIONS = 20
MONGO_AVG_MS_LIMIT = 100.0
ENDPOINT_AVG_MS_LIMIT = 200.0


def _avg_ms(samples: list[float]) -> float:
    return statistics.mean(samples)


@pytest.fixture
def perf_client():
    clear_dependency_caches()
    with TestClient(app) as c:
        yield c
    clear_dependency_caches()


class TestMongoPerformance:
    @pytest.mark.asyncio
    async def test_user_repo_find_by_email_avg_under_100ms(self):
        client = AsyncMongoMockClient()
        db = client["laria_perf"]
        repo = MongoDBUserRepository(database=db)
        user = UserAggregate.register("perf", "perf@example.com", "SecurePass1x")
        await repo.save(user)

        samples: list[float] = []
        for _ in range(ITERATIONS):
            start = time.perf_counter()
            found = await repo.find_by_email(Email("perf@example.com"))
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            samples.append(elapsed_ms)
            assert found is not None

        avg = _avg_ms(samples)
        assert avg < MONGO_AVG_MS_LIMIT, f"Mongo avg {avg:.2f}ms >= {MONGO_AVG_MS_LIMIT}ms"


class TestEndpointPerformance:
    def test_health_avg_under_200ms(self, perf_client: TestClient):
        samples: list[float] = []
        for _ in range(ITERATIONS):
            start = time.perf_counter()
            r = perf_client.get("/health")
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            samples.append(elapsed_ms)
            assert r.status_code == 200

        avg = _avg_ms(samples)
        assert avg < ENDPOINT_AVG_MS_LIMIT, f"/health avg {avg:.2f}ms >= {ENDPOINT_AVG_MS_LIMIT}ms"

    def test_register_avg_under_200ms(self, perf_client: TestClient):
        samples: list[float] = []
        for i in range(ITERATIONS):
            email = f"perf_{uuid4().hex[:8]}@example.com"
            username = f"perf_{i}_{uuid4().hex[:4]}"
            start = time.perf_counter()
            r = perf_client.post(
                "/api/v1/auth/register",
                json={"username": username, "email": email, "password": "SecurePass1x"},
            )
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            samples.append(elapsed_ms)
            assert r.status_code == 201

        avg = _avg_ms(samples)
        assert avg < ENDPOINT_AVG_MS_LIMIT, f"register avg {avg:.2f}ms >= {ENDPOINT_AVG_MS_LIMIT}ms"
