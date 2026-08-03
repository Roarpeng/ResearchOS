"""Unit tests for Gateway health endpoints."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Force deterministic Phase 1 defaults before app import side effects.
os.environ.setdefault("ENV", "dev")
os.environ.pop("DATABASE_URL", None)
os.environ.pop("REDIS_URL", None)


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    from gateway.app.config import get_settings

    get_settings.cache_clear()

    from gateway.app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()


def test_health_live_ok(client: TestClient) -> None:
    resp = client.get("/api/v1/health/live")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "X-Request-ID" in resp.headers


def test_health_ready_degraded_without_deps(client: TestClient) -> None:
    resp = client.get("/api/v1/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["checks"]["postgres"] == "skipped"
    assert body["checks"]["redis"] == "skipped"


def test_health_alias(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_request_id_propagated(client: TestClient) -> None:
    resp = client.get("/api/v1/health/live", headers={"X-Request-ID": "req_test_123"})
    assert resp.headers.get("X-Request-ID") == "req_test_123"
