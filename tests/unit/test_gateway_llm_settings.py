"""Unit tests for Gateway LLM settings — 5 fixed slots."""

from __future__ import annotations

import json
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


def test_get_llm_settings_default_one_per_kind(client: TestClient) -> None:
    res = client.get("/api/v1/settings/llm")
    assert res.status_code == 200
    data = res.json()["data"]
    ids = [s["id"] for s in data["slots"]]
    assert ids == ["chat_a", "embed", "rerank"]
    kinds = {s["id"]: s["kind"] for s in data["slots"]}
    assert kinds == {"chat_a": "chat", "embed": "embed", "rerank": "rerank"}
    assert data["agents"]["research"] == "chat_a"
    assert data["agents"]["researcher"] == "chat_a"
    assert data["agents"]["writer"] == "chat_a"
    assert all(s["primary"] is True for s in data["slots"])
    assert all(s["removable"] is False for s in data["slots"])


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


def test_put_omits_api_key_keeps_existing(client: TestClient) -> None:
    first = client.put(
        "/api/v1/settings/llm",
        json={
            "slots": {
                "chat_a": {
                    "api_key": "sk-keep-me-abcdef1234",
                    "model": "deepseek-chat",
                    "base_url": "https://api.deepseek.com",
                }
            }
        },
    )
    assert first.status_code == 200, first.text
    chat_a = next(s for s in first.json()["data"]["slots"] if s["id"] == "chat_a")
    assert chat_a["configured"] is True
    assert chat_a["base_url"] == "https://api.deepseek.com/v1"

    second = client.put(
        "/api/v1/settings/llm",
        json={
            "slots": {
                "chat_a": {"model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1"},
                "chat_b": {"model": "gpt-4o-mini", "base_url": "https://api.openai.com/v1"},
                "chat_c": {"model": "gpt-4o-mini", "base_url": "https://api.openai.com/v1"},
            }
        },
    )
    assert second.status_code == 200, second.text
    data = second.json()["data"]
    chat_a = next(s for s in data["slots"] if s["id"] == "chat_a")
    assert chat_a["configured"] is True
    assert "sk-keep-me-abcdef1234" not in str(data)
    chat_b = next(s for s in data["slots"] if s["id"] == "chat_b")
    assert chat_b["configured"] is False


def test_llm_slot_test_rejects_unknown(client: TestClient) -> None:
    res = client.post("/api/v1/settings/llm/test", json={"slot_id": "nope"})
    assert res.status_code == 400


def test_llm_slot_test_connectivity_ok(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from gateway.app.services import llm_settings as llm_svc

    class _Resp:
        status_code = 200
        text = '{"choices":[{"message":{"content":"pong"}}]}'

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, method, url, headers=None, json=None):
            assert method == "POST"
            assert "/chat/completions" in url
            return _Resp()

        def post(self, url, headers=None, json=None):
            return self.request("POST", url, headers=headers, json=json)

    monkeypatch.setattr(llm_svc, "_ipv4_http_client", lambda: _Client())
    res = client.post(
        "/api/v1/settings/llm/test",
        json={
            "slot_id": "chat_a",
            "api_key": "sk-test",
            "model": "gpt-test",
            "base_url": "https://api.example.com/v1",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["ok"] is True
    assert data["slot_id"] == "chat_a"
    assert "联通成功" in data["message"]


def test_normalize_deepseek_base_url_adds_v1() -> None:
    from gateway.app.services.llm_settings import (
        _chat_completion_urls,
        _normalize_openai_compatible_base,
    )

    assert _normalize_openai_compatible_base("https://api.deepseek.com") == (
        "https://api.deepseek.com/v1"
    )
    assert _normalize_openai_compatible_base("https://api.deepseek.com/v1") == (
        "https://api.deepseek.com/v1"
    )
    assert _normalize_openai_compatible_base(
        "https://api.deepseek.com/v1/chat/completions"
    ) == "https://api.deepseek.com/v1"
    urls = _chat_completion_urls("https://api.deepseek.com")
    assert urls[0] == "https://api.deepseek.com/v1/chat/completions"


def test_llm_slot_test_deepseek_root_without_v1(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from gateway.app.services import llm_settings as llm_svc

    seen: list[str] = []

    class _Resp:
        def __init__(self, code: int):
            self.status_code = code
            self.text = '{"choices":[{"message":{"content":"pong"}}]}' if code < 400 else "not found"

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, method, url, headers=None, json=None):
            seen.append(url)
            if "/v1/chat/completions" in url:
                return _Resp(200)
            return _Resp(404)

        def post(self, url, headers=None, json=None):
            return self.request("POST", url, headers=headers, json=json)

    monkeypatch.setattr(llm_svc, "_ipv4_http_client", lambda: _Client())
    res = client.post(
        "/api/v1/settings/llm/test",
        json={
            "slot_id": "chat_c",
            "api_key": "sk-deepseek-test",
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["ok"] is True
    assert any("/v1/chat/completions" in u for u in seen)
    assert data["base_url"] == "https://api.deepseek.com/v1"
    assert data["base_url"] == "https://api.deepseek.com/v1"


def test_llm_slot_test_persists_draft_so_refresh_keeps_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from gateway.app.services import llm_settings as llm_svc

    class _Resp:
        status_code = 200
        text = '{"choices":[{"message":{"content":"pong"}}]}'

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, method, url, headers=None, json=None):
            return _Resp()

        def post(self, url, headers=None, json=None):
            return self.request("POST", url, headers=headers, json=json)

    monkeypatch.setattr(llm_svc, "_ipv4_http_client", lambda: _Client())
    res = client.post(
        "/api/v1/settings/llm/test",
        json={
            "slot_id": "chat_a",
            "api_key": "sk-persist-refresh-abcdef",
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com",
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["ok"] is True

    loaded = client.get("/api/v1/settings/llm")
    assert loaded.status_code == 200
    data = loaded.json()["data"]
    chat_a = next(s for s in data["slots"] if s["id"] == "chat_a")
    assert chat_a["configured"] is True
    assert chat_a["model"] == "deepseek-chat"
    assert chat_a["base_url"] == "https://api.deepseek.com/v1"
    assert "sk-persist-refresh-abcdef" not in str(data)

    again = client.post("/api/v1/settings/llm/test", json={"slot_id": "chat_a"})
    assert again.status_code == 200, again.text
    assert again.json()["data"]["ok"] is True


def test_llm_slot_test_failure_does_not_persist(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from gateway.app.services import llm_settings as llm_svc

    class _Resp:
        status_code = 401
        text = '{"error":"invalid api key"}'

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, method, url, headers=None, json=None):
            return _Resp()

        def post(self, url, headers=None, json=None):
            return self.request("POST", url, headers=headers, json=json)

    monkeypatch.setattr(llm_svc, "_ipv4_http_client", lambda: _Client())
    monkeypatch.delenv("ROS_LLM_CHAT_A_API_KEY", raising=False)
    res = client.post(
        "/api/v1/settings/llm/test",
        json={
            "slot_id": "chat_a",
            "api_key": "sk-should-not-save",
            "model": "gpt-nope",
            "base_url": "https://api.example.com/v1",
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["ok"] is False

    keys_path = tmp_path / "llm" / "slot_keys.json"
    if keys_path.is_file():
        assert "sk-should-not-save" not in keys_path.read_text(encoding="utf-8")
    configs_path = tmp_path / "llm" / "slot_configs.json"
    if configs_path.is_file():
        assert "gpt-nope" not in configs_path.read_text(encoding="utf-8")

    loaded = client.get("/api/v1/settings/llm")
    chat_a = next(s for s in loaded.json()["data"]["slots"] if s["id"] == "chat_a")
    assert chat_a["model"] != "gpt-nope"


def test_llm_slot_test_missing_key(client: TestClient) -> None:
    res = client.post(
        "/api/v1/settings/llm/test",
        json={
            "slot_id": "chat_b",
            "model": "m",
            "base_url": "https://api.example.com/v1",
        },
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["ok"] is False
    assert "API Key" in data["message"]


def test_put_extra_embed_and_rerank_slots(client: TestClient) -> None:
    res = client.put(
        "/api/v1/settings/llm",
        json={
            "slots": {
                "embed_b": {
                    "api_key": "sk-embed-b-abcdef1234",
                    "model": "text-embedding-3-large",
                    "base_url": "https://api.openai.com/v1",
                },
                "rerank_b": {
                    "model": "bge-reranker-v2-m3",
                    "base_url": "http://127.0.0.1:8081",
                },
            },
            "agents": {
                "research": "chat_a",
                "planner": "chat_a",
                "researcher": "chat_a",
                "writer": "chat_a",
                "plc": "chat_a",
                "embed": "embed_b",
                "rerank": "rerank_b",
            },
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    embed_b = next(s for s in data["slots"] if s["id"] == "embed_b")
    rerank_b = next(s for s in data["slots"] if s["id"] == "rerank_b")
    assert embed_b["configured"] is True
    assert embed_b["model"] == "text-embedding-3-large"
    assert rerank_b["model"] == "bge-reranker-v2-m3"
    assert data["agents"]["embed"] == "embed_b"
    assert data["agents"]["rerank"] == "rerank_b"
    ids = {s["id"] for s in data["slots"]}
    assert "embed_b" in ids
    assert "rerank_b" in ids
    assert "chat_b" not in ids


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


def test_add_and_remove_custom_slots(client: TestClient) -> None:
    first = client.put("/api/v1/settings/llm", json={"add_slot": "chat"})
    assert first.status_code == 200, first.text
    ids = [s["id"] for s in first.json()["data"]["slots"]]
    assert ids.count("chat_a") == 1
    assert "chat_b" in ids
    assert "chat_c" not in ids
    chat_b = next(s for s in first.json()["data"]["slots"] if s["id"] == "chat_b")
    assert chat_b["removable"] is True
    assert chat_b["primary"] is False
    assert chat_b["configured"] is False

    second = client.put("/api/v1/settings/llm", json={"add_slot": "chat"})
    assert "chat_c" in {s["id"] for s in second.json()["data"]["slots"]}

    capped = client.put("/api/v1/settings/llm", json={"add_slot": "chat"})
    assert capped.status_code == 400

    embed = client.put("/api/v1/settings/llm", json={"add_slot": "embed"})
    assert embed.status_code == 200
    assert "embed_b" in {s["id"] for s in embed.json()["data"]["slots"]}

    removed = client.put("/api/v1/settings/llm", json={"remove_slot": "chat_b"})
    assert removed.status_code == 200
    left = {s["id"] for s in removed.json()["data"]["slots"]}
    assert "chat_b" not in left
    assert "chat_c" in left
    assert "chat_a" in left

    blocked = client.put("/api/v1/settings/llm", json={"remove_slot": "chat_a"})
    assert blocked.status_code == 400


def test_folds_configured_extra_into_empty_default(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "llm"
    root.mkdir(parents=True, exist_ok=True)
    (root / "settings.json").write_text(
        json.dumps(
            {
                "enabled_slots": ["chat_a", "chat_c", "embed", "rerank"],
                "agents": {
                    "research": "chat_c",
                    "planner": "chat_a",
                    "researcher": "chat_a",
                    "writer": "chat_c",
                    "plc": "chat_a",
                    "embed": "embed",
                    "rerank": "rerank",
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "slot_keys.json").write_text(
        json.dumps({"chat_c": "sk-1abcdefghijklmnopqrstuvwxyz-d570"}),
        encoding="utf-8",
    )
    (root / "slot_configs.json").write_text(
        json.dumps(
            {
                "chat_a": {"model": "gpt-4o-mini", "base_url": "https://api.openai.com/v1"},
                "chat_c": {"model": "deepseek-v4-flash", "base_url": "https://api.deepseek.com"},
            }
        ),
        encoding="utf-8",
    )

    res = client.get("/api/v1/settings/llm")
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    ids = [s["id"] for s in data["slots"]]
    assert ids == ["chat_a", "embed", "rerank"]
    chat_a = next(s for s in data["slots"] if s["id"] == "chat_a")
    assert chat_a["configured"] is True
    assert chat_a["model"] == "deepseek-v4-flash"
    assert "deepseek.com" in chat_a["base_url"]
    assert data["agents"]["research"] == "chat_a"
    assert data["agents"]["writer"] == "chat_a"
