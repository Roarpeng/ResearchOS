"""Meeting brief unit tests."""

from __future__ import annotations

from scientific.manuscript.brief import build_meeting_brief


def test_build_meeting_brief() -> None:
    notes = [
        {"text": "wheat nitrogen fertilizer response increased yield", "created_at": "2026-09-06"},
        {"text": "rice drought tolerance OsNAC gene", "created_at": "2026-09-05"},
        {"text": "wheat field trial sampling", "created_at": "2026-09-04"},
    ]
    out = build_meeting_brief(notes, top_n=2, keywords=5)
    assert "组会简报" in out["markdown"]
    assert len(out["recent"]) == 2
    assert out["recent"][0]["created_at"] == "2026-09-06"
    assert "wheat" in out["keywords"]


def test_brief_empty_notes() -> None:
    out = build_meeting_brief([])
    assert "(暂无笔记)" in out["markdown"]
    assert out["keywords"] == []
