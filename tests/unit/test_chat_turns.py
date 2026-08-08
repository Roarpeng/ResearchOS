"""Unified chat turn API tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ENV", "dev")

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "tia_exports"
FIXTURE_OB = FIXTURE_DIR / "Blocks" / "Main_OB1.xml"


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("DEV_API_KEY", "ros_ak_test_key")
    monkeypatch.setenv("PLC_PATH_ALLOWLIST", str(FIXTURE_DIR.parent.resolve()))
    monkeypatch.setenv("PLC_WORK_DIR", str(tmp_path / "plc_work"))
    from gateway.app.config import get_settings

    get_settings.cache_clear()
    from gateway.app.main import create_app
    from gateway.app.services import store as mem

    mem.store.tasks.clear()
    mem.store.plc_jobs.clear()
    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()
    mem.store.tasks.clear()
    mem.store.plc_jobs.clear()


def test_chat_research_route(client: TestClient) -> None:
    res = client.post(
        "/api/v1/chat/turns",
        data={"message": "对比协作机器人在力控上的差异"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["route"] == "research"
    assert data["task"]["id"]
    assert data["assistant_message"]


def test_chat_plc_block_name_focus(client: TestClient) -> None:
    """Deep-dive must honor block_name even when focus_node_id is a frontend-only id."""
    create = client.post(
        "/api/v1/chat/turns",
        files={"file": ("Main_OB1.xml", FIXTURE_OB.read_bytes(), "application/xml")},
        data={"message": "解析这个工程"},
    )
    assert create.status_code == 200, create.text
    task_id = create.json()["data"]["task"]["id"]
    # Use fixture block Main — name from parse
    detail = create.json()["data"]
    # Follow-up with mismatched focus id + explicit block_name
    follow = client.post(
        "/api/v1/chat/turns",
        data={
            "message": "@Main 请描述这个功能块的作用、输入输出与主要逻辑",
            "task_id": task_id,
            "focus_node_id": "plc_b_fake_Main",
            "block_name": "Main",
        },
    )
    assert follow.status_code == 200, follow.text
    ans = follow.json()["data"]["assistant_message"]
    assert "`Main`" in ans
    assert "作用：" in ans
    assert "ResearchOS PLC Intelligence" not in ans
    assert "工程概览" not in ans
    assert "针对你的问题" not in ans

    res = client.post(
        "/api/v1/chat/turns",
        data={"message": "解释一下这个 PLC 的 OB1 调用关系"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["route"] == "plc"
    assert data["plc_job_id"] is None
    assert "路径" in data["assistant_message"] or "上传" in data["assistant_message"] or "工程" in data["assistant_message"]


def test_chat_plc_path_and_followup(client: TestClient) -> None:
    assert FIXTURE_OB.is_file()
    res = client.post(
        "/api/v1/chat/turns",
        data={"message": f"解析 {FIXTURE_OB}"},
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["route"] == "plc"
    assert data["plc_job_id"]
    assert "检测" in data["assistant_message"] or "西门子" in data["assistant_message"]
    assert "解析过程" not in data["assistant_message"]
    canvas = data.get("knowledge_canvas") or data["task"]["result"].get("knowledge_canvas") or {}
    nodes = canvas.get("nodes") or []
    assert any(n.get("kind") == "plc_block" or n.get("kind") == "plc_project" for n in nodes), nodes
    task_id = data["task"]["id"]

    # Second turn must still keep / refresh PLC nodes on canvas
    follow = client.post(
        "/api/v1/chat/turns",
        data={"message": "有哪些块？", "task_id": task_id},
    )
    assert follow.status_code == 200
    assert follow.json()["data"]["route"] == "plc"
    assert follow.json()["data"]["assistant_message"]
    canvas2 = follow.json()["data"].get("knowledge_canvas") or {}
    assert any(
        n.get("kind") in {"plc_block", "plc_project"} for n in (canvas2.get("nodes") or [])
    )
