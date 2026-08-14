"""Hub catalog + knowledge service smoke tests (offline-safe)."""

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
    monkeypatch.setenv("LOCAL_OBJECTS_DIR", str(tmp_path / "objects"))
    monkeypatch.setenv("PLC_WORK_DIR", str(tmp_path / "plc"))
    from gateway.app.config import get_settings
    from knowledge.settings import get_settings as kg_settings
    from knowledge.store import reset_registry

    get_settings.cache_clear()
    kg_settings.cache_clear()
    reset_registry()
    from gateway.app.main import create_app
    from gateway.app.services import store as mem

    mem.store.spaces.clear()
    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()
    kg_settings.cache_clear()


def test_hub_mcp_search_and_install_fallback(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from gateway.app.services import hub_catalog as hub

    def boom(*_a, **_k):
        raise OSError("offline")

    monkeypatch.setattr(hub, "_http_get_json", boom)
    res = client.get("/api/v1/settings/hub/mcp", params={"query": "filesystem"})
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["offline"] is True
    assert data["items"]
    item = data["items"][0]
    inst = client.post("/api/v1/settings/hub/mcp/install", json={"item": item})
    assert inst.status_code == 200, inst.text
    names = [m["name"] for m in inst.json()["data"]["mcp_servers"]]
    assert any("filesystem" in n or "server-filesystem" in n or n for n in names)


def test_hub_skills_fallback_install(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from gateway.app.services import hub_catalog as hub

    def boom(*_a, **_k):
        raise OSError("offline")

    monkeypatch.setattr(hub, "_http_get_json", boom)
    monkeypatch.setattr(hub, "_http_get_text", boom)
    monkeypatch.chdir(tmp_path)
    res = client.get("/api/v1/settings/hub/skills", params={"query": "docx"})
    assert res.status_code == 200, res.text
    item = res.json()["data"]["items"][0]
    inst = client.post("/api/v1/settings/hub/skills/install", json={"item": item})
    assert inst.status_code == 200, inst.text
    skills = inst.json()["data"]["skills"]
    assert skills
    skill_dir = tmp_path / ".agents" / "skills" / skills[0]["name"]
    assert (skill_dir / "SKILL.md").is_file()


def test_knowledge_ingest_stats_search(client: TestClient) -> None:
    space = client.post(
        "/api/v1/knowledge/spaces",
        json={"name": "demo-kb", "description": "unit"},
    )
    assert space.status_code == 201, space.text
    kb_id = space.json()["data"]["id"]
    up = client.post(
        f"/api/v1/knowledge/spaces/{kb_id}/documents",
        files={"file": ("note.md", b"# RS-200\n\nRated torque 12 Nm.\n", "text/markdown")},
    )
    assert up.status_code == 202, up.text
    body = up.json()["data"]
    assert body["chunk_count"] >= 1
    assert body["status"] in {"ready", "ready_degraded", "failed", "queued"}

    stats = client.get(f"/api/v1/knowledge/spaces/{kb_id}/stats")
    assert stats.status_code == 200
    assert stats.json()["data"]["document_count"] >= 1

    search = client.post(
        "/api/v1/knowledge/search",
        json={"query": "torque RS-200", "knowledge_space_ids": [kb_id], "top_k": 5},
    )
    assert search.status_code == 200, search.text
    assert "retrieved" in (search.json()["data"].get("message") or "")

    chunks = client.get(f"/api/v1/knowledge/spaces/{kb_id}/chunks", params={"limit": 20})
    assert chunks.status_code == 200, chunks.text
    chunk_body = chunks.json()["data"]
    assert chunk_body["count"] >= 1
    first = chunk_body["chunks"][0]
    assert first.get("text")
    assert "has_vector" in first

    by_doc = client.get(
        f"/api/v1/knowledge/spaces/{kb_id}/chunks",
        params={"doc_id": body["id"], "limit": 20},
    )
    assert by_doc.status_code == 200
    assert by_doc.json()["data"]["count"] >= 1

    vector_search = client.post(
        "/api/v1/knowledge/search",
        json={
            "query": "torque RS-200",
            "knowledge_space_ids": [kb_id],
            "top_k": 5,
            "mode": "vector",
        },
    )
    assert vector_search.status_code == 200, vector_search.text
    vmsg = vector_search.json()["data"].get("message") or ""
    assert "vector" in vmsg.lower() or "retrieved" in vmsg

    rebuild = client.post(f"/api/v1/knowledge/spaces/{kb_id}/rebuild")
    assert rebuild.status_code == 200
    assert rebuild.json()["data"]["ok"] is True
