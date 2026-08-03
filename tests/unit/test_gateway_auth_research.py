"""Unit tests for auth / session stubs."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ENV", "dev")


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("DEV_API_KEY", "ros_ak_test_key")
    from gateway.app.config import get_settings

    get_settings.cache_clear()
    from gateway.app.main import create_app

    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()


def test_login_and_me(client: TestClient) -> None:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "dev@example.com", "password": "x"},
    )
    assert login.status_code == 200
    data = login.json()["data"]
    assert data["access_token"]
    assert data["refresh_token"].startswith("rt_")

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["ok"] is True


def test_api_key_header(client: TestClient) -> None:
    resp = client.get("/api/v1/auth/me", headers={"X-API-Key": "ros_ak_test_key"})
    assert resp.status_code == 200
    assert resp.json()["data"]["auth_type"] == "api_key"


def test_create_research_task_local_echo(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/research/tasks",
        json={"query": "smoke research question"},
        headers={"X-API-Key": "ros_ak_test_key"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["id"].startswith("tsk_")
    assert body["data"]["stream"]["ws_url"].startswith("/api/v1/ws/research/")
