"""Adapters mapping the manuscript domain onto the writer/reviewer node contracts.

These are the deterministic half of the R2 runtime glue: the runtime supervisor can
route manuscript tasks through `reviewer_manuscript` / `writer_manuscript` with the
same return shape as agents/reviewer:run and agents/writer:run. The LLM generation
step (research/analysis producing `manuscript_chunks`) remains model-dependent.
"""

from __future__ import annotations

from typing import Any

from scientific.manuscript.draft import assemble_sections
from scientific.manuscript.journalize import render_markdown
from scientific.manuscript.prompts import AI_DISCLOSURE_TEMPLATE
from scientific.manuscript.provenance.record import ProvenanceRecord
from scientific.manuscript.release_gate import run_release_gate

_DEFAULT_OUTLINE = {
    "sections": [
        {"key": "introduction", "title": "Introduction"},
        {"key": "results", "title": "Results"},
        {"key": "discussion", "title": "Discussion"},
    ]
}


def _records(state: dict[str, Any]) -> list[ProvenanceRecord]:
    raw = state.get("manuscript_records") or []
    return [r if isinstance(r, ProvenanceRecord) else ProvenanceRecord.from_dict(r) for r in raw]


def reviewer_manuscript(state: dict[str, Any]) -> dict[str, Any]:
    """Manuscript Reviewer: release gate over provenance records (phantom/unsourced/disclosure)."""
    records = _records(state)
    ai_disclosure = bool((state.get("meta") or {}).get("ai_disclosure", True))
    scholar_verify = state.get("scholar_verify")
    gate = run_release_gate(records, ai_disclosure=ai_disclosure, scholar_verify=scholar_verify)
    verdict = "pass" if gate.passed else "reject"
    return {
        "review": {"verdict": verdict, "reasons": gate.reasons, "gaps": []},
        "route": "writer" if gate.passed else "research",
        "meta": {"manuscript_gate": {"passed": gate.passed}},
    }


def writer_manuscript(state: dict[str, Any]) -> dict[str, Any]:
    """Manuscript Writer: assemble sections from chunks + render canonical Markdown."""
    outline = state.get("manuscript_outline") or _DEFAULT_OUTLINE
    chunks = state.get("manuscript_chunks") or []
    sections = assemble_sections(outline, chunks)

    goal = state.get("goal") or {}
    meta = state.get("meta") or {}
    title = goal.get("raw_query") or goal.get("normalized_objective") or "Manuscript"
    markdown = render_markdown(
        title=str(title),
        authors=[str(a) for a in (meta.get("authors") or [])],
        abstract=str(state.get("manuscript_abstract") or ""),
        sections=sections,
        ai_disclosure=AI_DISCLOSURE_TEMPLATE,
        references=[str(r) for r in (state.get("references") or [])],
    )
    return {
        "result": markdown,
        "route": "memory",
        "meta": {"writer_completed": True, "report_format": "markdown"},
    }
