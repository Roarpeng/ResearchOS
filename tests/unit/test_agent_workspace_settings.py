"""Agent workspace settings (tools / MCP / skills)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ENV", "dev")


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("DEV_API_KEY", "ros_ak_test_key")
    monkeypatch.setenv("AGENT_WORKSPACE_SETTINGS_PATH", str(tmp_path / "agent_workspace.json"))
    from gateway.app.config import get_settings

    get_settings.cache_clear()
    from gateway.app.main import create_app

    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()


def test_agent_workspace_defaults_and_update(client: TestClient) -> None:
    got = client.get("/api/v1/settings/agent-workspace")
    assert got.status_code == 200, got.text
    data = got.json()["data"]
    assert data["tools"]
    assert data["mcp_servers"] == []
    assert data["skills"] == []

    put = client.put(
        "/api/v1/settings/agent-workspace",
        json={
            "mcp_servers": [
                {
                    "name": "graphflow",
                    "transport": "stdio",
                    "command": "npx graphflow",
                    "enabled": True,
                }
            ],
            "skills": [{"name": "animate", "path": ".agents/skills/animate", "enabled": True}],
        },
    )
    assert put.status_code == 200, put.text
    body = put.json()["data"]
    assert body["mcp_servers"][0]["name"] == "graphflow"
    assert body["skills"][0]["name"] == "animate"
    assert any(t["name"] == "web_search" for t in body["tools"])
