"""Unified chat turn API tests."""

from __future__ import annotations

import os
import time
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


def _wait_job_ready(client: TestClient, job_id: str, *, timeout_s: float = 30.0) -> dict:
    deadline = time.time() + timeout_s
    last: dict = {}
    while time.time() < deadline:
        res = client.get(f"/api/v1/plc/jobs/{job_id}")
        assert res.status_code == 200, res.text
        last = res.json()["data"]
        if last.get("status") in {"ready", "failed"}:
            return last
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} not ready: {last}")


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
    create_data = create.json()["data"]
    task_id = create_data["task"]["id"]
    job_id = create_data["plc_job_id"]
    assert job_id
    assert "已接收" in create_data["assistant_message"] or "正在解析" in create_data["assistant_message"]
    job = _wait_job_ready(client, job_id)
    assert job["status"] == "ready", job

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
    assert "已接收" in data["assistant_message"] or "正在解析" in data["assistant_message"]
    job = _wait_job_ready(client, data["plc_job_id"])
    assert job["status"] == "ready", job
    task_id = data["task"]["id"]
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
    ), canvas2


def test_chat_plc_upload_returns_before_ingest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Chat turn must return queued/pending before ingest runs when schedule is deferred."""
    import asyncio

    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("DEV_API_KEY", "ros_ak_test_key")
    monkeypatch.setenv("PLC_PATH_ALLOWLIST", str(FIXTURE_DIR.parent.resolve()))
    monkeypatch.setenv("PLC_WORK_DIR", str(tmp_path / "plc_work"))
    from gateway.app.config import get_settings

    get_settings.cache_clear()
    from gateway.app.services import chat_turns
    from gateway.app.services import plc_jobs as plc
    from gateway.app.services import store as mem
    from gateway.app.services.runtime_client import RuntimeClient

    mem.store.tasks.clear()
    mem.store.plc_jobs.clear()

    ingest_started = {"n": 0}
    deferred: list = []

    def schedule(fn) -> None:  # noqa: ANN001
        deferred.append(fn)

    real_ingest = plc.run_ingest_job

    def tracking_ingest(job_id: str, **kwargs):  # noqa: ANN001
        ingest_started["n"] += 1
        return real_ingest(job_id, **kwargs)

    monkeypatch.setattr(plc, "run_ingest_job", tracking_ingest)
    monkeypatch.setattr(chat_turns.plc, "run_ingest_job", tracking_ingest)

    async def _run() -> dict:
        return await chat_turns.handle_chat_turn(
            message="解析这个工程",
            principal_subject="test",
            workspace_id=None,
            session_id=None,
            request_id="req_test",
            runtime=RuntimeClient(base_url="http://127.0.0.1:9"),
            upload_bytes=FIXTURE_OB.read_bytes(),
            upload_filename="Main_OB1.xml",
            schedule_ingest=schedule,
        )

    result = asyncio.run(_run())
    assert result["route"] == "plc"
    job = result["plc_job"]
    assert job is not None
    assert job["status"] == "queued"
    assert ingest_started["n"] == 0
    assert "正在解析" in result["assistant_message"] or "已接收" in result["assistant_message"]
    assert result["task"]["plc_job_id"] == job["id"]
    assert len(deferred) == 1

    # Now run the scheduled ingest — should complete and refresh welcome
    deferred[0]()
    assert ingest_started["n"] == 1
    refreshed = plc.get_job(job["id"])
    assert refreshed is not None
    assert refreshed["status"] == "ready"
    assert refreshed["blocks"]
    assistant_turns = [c for c in (refreshed.get("chat") or []) if c.get("role") == "assistant"]
    assert assistant_turns
    assert "画布已更新" in assistant_turns[0]["content"] or "程序块" in assistant_turns[0]["content"]

    mem.store.tasks.clear()
    mem.store.plc_jobs.clear()
    get_settings.cache_clear()


def test_chat_plc_need_source(client: TestClient) -> None:
    res = client.post(
        "/api/v1/chat/turns",
        data={"message": "解释一下这个 PLC 的 OB1 调用关系"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["route"] == "plc"
    assert data["plc_job_id"] is None
    assert "路径" in data["assistant_message"] or "上传" in data["assistant_message"] or "工程" in data["assistant_message"]
