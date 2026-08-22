"""Unit tests: Reviewer citation gate, contradiction + criteria heuristics."""

from __future__ import annotations

from agents.research.node import run as research_run
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


def _contradictions(out):
    return [
        r
        for r in out["review"]["reasons"]
        if isinstance(r, dict) and r.get("kind") == "contradiction"
    ]


def test_reviewer_detects_numeric_contradiction():
    state = initial_state("tsk_rev_cn", "compare cobots")
    state["evidence"] = [
        {
            "id": "ev_1",
            "title": "Official spec",
            "content": "Model X 防护等级 IP67",
            "url": "https://example.com/a",
        },
        {
            "id": "ev_2",
            "title": "Third-party review",
            "content": "Model X 防护等级 IP65",
            "url": "https://example.com/b",
        },
    ]
    state["citations"] = [
        {"id": "C1", "evidence_id": "ev_1", "title": "Official spec", "url": "https://example.com/a"},
        {"id": "C2", "evidence_id": "ev_2", "title": "Third-party review", "url": "https://example.com/b"},
    ]
    state["analysis_results"] = {
        "specs": {
            "specialty": "specs",
            "content": "Model X 防护等级 IP67 与 IP65 存在差异",
            "citation_ids": ["C1", "C2"],
            "gaps": [],
        }
    }

    out = reviewer_run(state)
    assert out["review"]["verdict"] == "reject"
    contradictions = _contradictions(out)
    assert contradictions
    assert set(contradictions[0]["evidence_ids"]) == {"ev_1", "ev_2"}
    assert "contradiction" in out["review"]["gaps"]
    # Directed re-search follow-up emitted with a query
    assert any(f["query"] for f in out["meta"]["review_followups"])


def test_reviewer_detects_polarity_contradiction():
    state = initial_state("tsk_rev_cp", "feasibility")
    state["evidence"] = [
        {
            "id": "ev_1",
            "title": "Study A",
            "content": "该方案可行",
            "url": "https://example.com/a",
        },
        {
            "id": "ev_2",
            "title": "Study B",
            "content": "该方案不可行",
            "url": "https://example.com/b",
        },
    ]
    state["citations"] = [
        {"id": "C1", "evidence_id": "ev_1", "title": "Study A", "url": "https://example.com/a"},
        {"id": "C2", "evidence_id": "ev_2", "title": "Study B", "url": "https://example.com/b"},
    ]
    state["analysis_results"] = {
        "decision": {
            "specialty": "decision",
            "content": "该方案可行性存在分歧",
            "citation_ids": ["C1", "C2"],
            "gaps": [],
        }
    }

    out = reviewer_run(state)
    contradictions = _contradictions(out)
    assert contradictions
    assert set(contradictions[0]["evidence_ids"]) == {"ev_1", "ev_2"}
    assert out["review"]["verdict"] == "reject"


def test_reviewer_checks_success_criteria_and_emits_followups():
    state = initial_state("tsk_rev_sc", "cobot selection")
    state["goal"]["success_criteria"] = ["覆盖厂商", "包含价格对比"]
    state["evidence"] = [
        {"id": "ev_1", "title": "Doc", "content": "覆盖三家主要厂商", "url": "https://example.com/a"}
    ]
    state["citations"] = [
        {"id": "C1", "evidence_id": "ev_1", "title": "Doc", "url": "https://example.com/a"}
    ]
    state["analysis_results"] = {
        "competitors": {
            "specialty": "competitors",
            "content": "覆盖三家主要厂商",
            "citation_ids": ["C1"],
            "gaps": [],
        }
    }

    out = reviewer_run(state)
    gaps = out["review"]["gaps"]
    # "覆盖厂商" hit; "包含价格对比" did not
    assert any(g.startswith("success_criteria_unmet::") and "价格对比" in g for g in gaps)
    assert not any("覆盖厂商" in g for g in gaps)
    # unmet criterion becomes a directed research follow-up
    followups = out["meta"]["review_followups"]
    assert any(f["specialty"] == "research" and f["query"] == "包含价格对比" for f in followups)


def test_research_consumes_review_followups():
    state = initial_state("tsk_followup", "协作机器人")
    state["meta"] = {
        "review_followups": [
            {"specialty": "research", "query": "IP67 防护等级 官方参数", "priority": 1}
        ]
    }
    out = research_run(state)
    assert out["evidence"]
    # follow-up evidence is tagged and the follow-up queue is cleared
    assert any((e.get("meta") or {}).get("followup") for e in out["evidence"])
    assert out["meta"]["review_followups"] == []
