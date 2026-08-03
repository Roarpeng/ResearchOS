"""Unit tests: Writer markdown output."""

from __future__ import annotations

from agents.writer.node import run as writer_run
from runtime.researchos_runtime.state import initial_state


def test_writer_emits_markdown_with_citation_markers():
    state = initial_state("tsk_w_1", "协作机器人选型")
    state["review"] = {"verdict": "pass", "reasons": [], "gaps": [], "citation_issues": []}
    state["citations"] = [
        {
            "id": "C1",
            "evidence_id": "ev_1",
            "title": "Safety brief",
            "url": "https://example.com/safety",
            "quote": "ISO 10218",
        },
        {
            "id": "C2",
            "evidence_id": "ev_2",
            "title": "Force control note",
            "url": "https://example.com/force",
            "quote": "ft sensor",
        },
    ]
    state["analysis_results"] = {
        "competitors": {
            "specialty": "competitors",
            "content": "## Competitors\nTwo vendors dominate force-limited modes.",
            "citation_ids": ["C1", "C2"],
            "gaps": [],
        },
        "decision": {
            "specialty": "decision",
            "content": "## Decision\nShortlist both vendors for pilot.",
            "citation_ids": ["C1"],
            "gaps": [],
        },
    }
    state["meta"] = {"citation_style": "footnote"}

    out = writer_run(state)
    md = out["result"]
    assert md is not None
    assert md.startswith("---")
    assert "# ResearchOS Report" in md
    assert "[^C1]" in md
    assert "[^C2]" in md
    assert "## 引用与来源" in md
    assert "[^C1]: Safety brief" in md
    assert out["route"] == "memory"


def test_writer_bracket_style():
    state = initial_state("tsk_w_2", "topic")
    state["review"] = {"verdict": "pass", "reasons": [], "gaps": [], "citation_issues": []}
    state["citations"] = [
        {"id": "C1", "title": "T", "url": "https://example.com", "quote": "q"}
    ]
    state["analysis_results"] = {
        "risks": {
            "specialty": "risks",
            "content": "Supply risk noted.",
            "citation_ids": ["C1"],
            "gaps": [],
        }
    }
    state["meta"] = {"citation_style": "bracket"}

    out = writer_run(state)
    assert "[citation:C1]" in out["result"]
