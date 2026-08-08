"""Unit tests for Gateway LLM settings — 5 fixed slots."""

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
    monkeypatch.setenv("LLM_SETTINGS_PATH", str(tmp_path / "llm" / "settings.json"))
    from gateway.app.config import get_settings

    get_settings.cache_clear()
    from gateway.app.main import create_app

    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()


def test_get_llm_settings_five_slots(client: TestClient) -> None:
    res = client.get("/api/v1/settings/llm")
    assert res.status_code == 200
    data = res.json()["data"]
    ids = {s["id"] for s in data["slots"]}
    assert ids == {"chat_a", "chat_b", "chat_c", "embed", "rerank"}
    kinds = {s["id"]: s["kind"] for s in data["slots"]}
    assert kinds["chat_a"] == "chat"
    assert kinds["embed"] == "embed"
    assert kinds["rerank"] == "rerank"
    assert data["agents"]["research"] == "chat_a"


def test_put_agent_bindings_to_chat_slots(client: TestClient) -> None:
    res = client.put(
        "/api/v1/settings/llm",
        json={
            "agents": {
                "research": "chat_b",
                "planner": "chat_a",
                "researcher": "chat_b",
                "writer": "chat_c",
                "plc": "chat_a",
                "embed": "embed",
                "rerank": "rerank",
            }
        },
    )
    assert res.status_code == 200
    assert res.json()["data"]["agents"]["research"] == "chat_b"


def test_put_rejects_unknown_slot(client: TestClient) -> None:
    res = client.put(
        "/api/v1/settings/llm",
        json={
            "agents": {
                "research": "not-a-slot",
                "planner": "chat_a",
                "researcher": "chat_b",
                "writer": "chat_c",
                "plc": "chat_a",
                "embed": "embed",
                "rerank": "rerank",
            }
        },
    )
    # unknown normalized away or 400 — either way must not stick as not-a-slot
    if res.status_code == 200:
        assert res.json()["data"]["agents"]["research"] != "not-a-slot"
    else:
        assert res.status_code == 400


def test_put_slot_model_base_url_and_key(client: TestClient) -> None:
    res = client.put(
        "/api/v1/settings/llm",
        json={
            "slots": {
                "chat_a": {
                    "api_key": "sk-test-chat-a-abcdef",
                    "model": "gpt-4o",
                    "base_url": "https://proxy.example.com/v1",
                },
                "rerank": {
                    "model": "bge-reranker-v2-m3",
                    "base_url": "http://127.0.0.1:8080",
                },
            }
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    chat_a = next(s for s in data["slots"] if s["id"] == "chat_a")
    rerank = next(s for s in data["slots"] if s["id"] == "rerank")
    assert chat_a["model"] == "gpt-4o"
    assert chat_a["base_url"] == "https://proxy.example.com/v1"
    assert chat_a["configured"] is True
    assert "sk-test-chat-a-abcdef" not in str(data)
    assert rerank["model"] == "bge-reranker-v2-m3"


def test_research_create_uses_saved_binding(client: TestClient) -> None:
    client.put(
        "/api/v1/settings/llm",
        json={
            "agents": {
                "research": "chat_c",
                "planner": "chat_a",
                "researcher": "chat_b",
                "writer": "chat_c",
                "plc": "chat_b",
                "embed": "embed",
                "rerank": "rerank",
            }
        },
    )
    res = client.post(
        "/api/v1/research/tasks",
        json={
            "query": "test llm binding",
            "mode": "quick",
            "options": {"model_profile": "default"},
        },
        headers={"X-API-Key": "ros_ak_test_key"},
    )
    assert res.status_code == 201
    assert res.json()["data"]["options"]["model_profile"] == "chat_c"
