"""Gateway API for Q1 device/sensor cards and Project Brief."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ENV", "dev")

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "tia_exports"
AUTH = {"X-API-Key": "ros_ak_test_key"}


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

    mem.store.plc_jobs.clear()
    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()
    mem.store.plc_jobs.clear()


def _ready_job(client: TestClient) -> str:
    create = client.post(
        "/api/v1/plc/jobs",
        json={"path": str(FIXTURE_DIR), "project_name": "MotorDemo", "publish_graph": False},
        headers=AUTH,
    )
    assert create.status_code == 202, create.text
    job_id = create.json()["data"]["id"]
    detail = client.get(f"/api/v1/plc/jobs/{job_id}", headers=AUTH)
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == "ready"
    return job_id


def test_device_cards_and_brief_and_annotation(client: TestClient) -> None:
    job_id = _ready_job(client)
    listing = client.get(f"/api/v1/plc/jobs/{job_id}/device-cards", headers=AUTH)
    assert listing.status_code == 200, listing.text
    body = listing.json()["data"]
    assert body["schema"] == "researchos.device_sensor_card.v1"
    names = {c["symbol_name"]: c for c in body["cards"]}
    assert "StartCmd" in names
    start = names["StartCmd"]
    assert start["meaning_status"] == "cited"
    assert start["meaning_text"] == "HMI start pushbutton"
    assert start["io_type"] == "DI"

    one = client.get(f"/api/v1/plc/jobs/{job_id}/device-cards/tag/StartCmd", headers=AUTH)
    assert one.status_code == 200
    assert one.json()["data"]["id"] == "tag:StartCmd"

    brief = client.get(f"/api/v1/plc/jobs/{job_id}/brief", headers=AUTH)
    assert brief.status_code == 200, brief.text
    b = brief.json()["data"]
    assert b["schema"] == "researchos.project_brief.v1"
    section = b["sections"]["device_sensor_summary"]
    assert section["schema"] == "researchos.brief.device_sensor_summary.v1"
    assert section["owned_by"] == "Q1"
    assert any(row["id"] == "tag:StartCmd" for row in section["cards"])

    put = client.put(
        f"/api/v1/plc/jobs/{job_id}/device-cards/tag/StartCmd/annotation",
        json={"text": "机台启动按钮", "author": "handover"},
        headers=AUTH,
    )
    assert put.status_code == 200, put.text
    annotated = put.json()["data"]
    assert annotated["meaning_status"] == "annotated"
    assert annotated["meaning_text"] == "机台启动按钮"
    assert annotated["comment"] == "HMI start pushbutton"

    missing = client.get(f"/api/v1/plc/jobs/{job_id}/device-cards/tag/NoSuchTag", headers=AUTH)
    assert missing.status_code == 404
