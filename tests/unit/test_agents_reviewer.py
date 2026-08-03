"""Unit tests: Reviewer citation gate."""

from __future__ import annotations

from agents.reviewer.node import run as reviewer_run
from runtime.researchos_runtime.state import initial_state


def test_reviewer_rejects_when_analysis_lacks_citations():
    state = initial_state("tsk_rev_1", "compare cobots")
    state["evidence"] = [
        {
            "id": "ev_1",
            "title": "Doc",
            "content": "IP67 rating claimed",
            "url": "https://example.com/a",
        }
    ]
    state["citations"] = [
        {"id": "C1", "evidence_id": "ev_1", "title": "Doc", "url": "https://example.com/a"}
    ]
    state["analysis_results"] = {
        "competitors": {
            "specialty": "competitors",
            "content": "Vendor A leads in force control and safety certification.",
            "citation_ids": [],
            "gaps": [],
        }
    }

    out = reviewer_run(state)
    assert out["review"]["verdict"] == "reject"
    assert "missing_citations" in out["review"]["gaps"]


def test_reviewer_passes_with_evidence_citations_and_refs():
    state = initial_state("tsk_rev_2", "compare cobots")
    state["evidence"] = [
        {
            "id": "ev_1",
            "title": "Doc",
            "content": "ISO 10218 referenced",
            "url": "https://example.com/a",
        }
    ]
    state["citations"] = [
        {
            "id": "C1",
            "evidence_id": "ev_1",
            "title": "Doc",
            "url": "https://example.com/a",
            "quote": "ISO 10218",
        }
    ]
    state["analysis_results"] = {
        "decision": {
            "specialty": "decision",
            "content": "Recommend shortlist based on certified force control.",
            "citation_ids": ["C1"],
            "gaps": [],
        }
    }

    out = reviewer_run(state)
    assert out["review"]["verdict"] == "pass"
    assert out["route"] == "writer"


def test_reviewer_rejects_empty_evidence():
    state = initial_state("tsk_rev_3", "empty")
    state["analysis_results"] = {
        "risks": {
            "specialty": "risks",
            "content": "Risk list",
            "citation_ids": ["C1"],
            "gaps": [],
        }
    }
    out = reviewer_run(state)
    assert out["review"]["verdict"] == "reject"
    assert "missing_evidence" in out["review"]["gaps"]
