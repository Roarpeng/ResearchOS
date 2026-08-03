"""Contract tests for Gateway health surface."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ENV", "dev")


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    from gateway.app.config import get_settings

    get_settings.cache_clear()
    from gateway.app.main import create_app

    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()


def test_health_contract_shapes(client: TestClient) -> None:
    live = client.get("/api/v1/health/live").json()
    assert set(live.keys()) >= {"status"}

    ready = client.get("/api/v1/health/ready").json()
    assert "status" in ready
    assert "checks" in ready
    assert isinstance(ready["checks"], dict)
    for key in ("postgres", "redis"):
        assert key in ready["checks"]
