"""Manuscript agent adapter tests (deterministic, no LLM)."""

from __future__ import annotations

from scientific.manuscript.agent_adapter import reviewer_manuscript, writer_manuscript
from scientific.manuscript.provenance.record import ProvenanceRecord, SourceRef


def _rec(claim_id: str, *, doi: str | None = None, sourced: bool = True) -> ProvenanceRecord:
    sources = [SourceRef(source_id="doc_1", chunk_ids=["chk_1"], doi=doi)] if sourced else []
    return ProvenanceRecord(
        claim_id=claim_id, claim_text="c", created_at="2026-09-06T00:00:00Z", sources=sources
    )


def test_reviewer_manuscript_pass() -> None:
    state = {"manuscript_records": [_rec("c1")], "scholar_verify": lambda d: {"doi": d}}
    out = reviewer_manuscript(state)
    assert out["review"]["verdict"] == "pass"
    assert out["route"] == "writer"


def test_reviewer_manuscript_reject_phantom() -> None:
    state = {"manuscript_records": [_rec("c1", doi="10.1/x")], "scholar_verify": lambda d: {"phantom": 1}}
    out = reviewer_manuscript(state)
    assert out["review"]["verdict"] == "reject"
    assert out["route"] == "research"


def test_writer_manuscript_renders_markdown() -> None:
    state = {
        "goal": {"raw_query": "Wheat nitrogen response"},
        "manuscript_outline": {"sections": [{"key": "results", "title": "Results"}]},
        "manuscript_chunks": [
            {"section": "results", "source_id": "doc_1", "chunk_id": "chk_1", "text": "wheat yield +12%"},
        ],
        "meta": {"authors": ["A. Li"]},
    }
    out = writer_manuscript(state)
    assert "## Results" in out["result"]
    assert "AI Use Disclosure" in out["result"]
    assert out["meta"]["report_format"] == "markdown"
