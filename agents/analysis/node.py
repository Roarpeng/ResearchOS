"""Analysis Agent node: competitors / risks / decision specialties."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from runtime.researchos_runtime.state import TaskState

DEFAULT_SPECIALTIES = ("competitors", "risks", "decision")


def _evidence_summary(evidence: list[dict[str, Any]], max_items: int = 3) -> str:
    parts: list[str] = []
    for item in evidence[:max_items]:
        title = item.get("title") or item.get("id") or "source"
        snippet = (item.get("content") or "")[:180]
        parts.append(f"- {title}: {snippet}")
    return "\n".join(parts) if parts else "- (no evidence)"


def _citation_placeholders(evidence: list[dict[str, Any]]) -> list[str]:
    """Temporary refs mapped later by Citation Agent to C1..Cn."""
    return [f"TMP:{item.get('id')}" for item in evidence if item.get("id")]


def run(state: TaskState) -> dict[str, Any]:
    goal = state.get("goal") or {}
    query = goal.get("raw_query") or goal.get("normalized_objective") or "topic"
    evidence = list(state.get("evidence") or [])
    specialties = list(goal.get("priority_specialties") or DEFAULT_SPECIALTIES)
    # Keep MVP specialty set focused
    allowed = {"competitors", "risks", "decision"}
    specialties = [s for s in specialties if s in allowed] or list(DEFAULT_SPECIALTIES)

    cite_ids = _citation_placeholders(evidence)
    summary = _evidence_summary(evidence)
    now = datetime.now(timezone.utc).isoformat()
    blocks: dict[str, dict[str, Any]] = {}

    for specialty in specialties:
        if specialty == "competitors":
            content = (
                f"## Competitors\n"
                f"Based on available evidence for «{query}»:\n{summary}\n\n"
                f"Key players appear across manufacturer docs, industry reports, "
                f"and secondary commentary. Positioning should be validated against "
                f"primary sources before procurement decisions."
            )
            gaps = [] if evidence else ["missing_competitors: no evidence collected"]
        elif specialty == "risks":
            content = (
                f"## Risks\n"
                f"Risk scan for «{query}»:\n{summary}\n\n"
                f"- Supply / vendor concentration risk if relying on a single OEM.\n"
                f"- Compliance risk if standards citations are incomplete.\n"
                f"- Data freshness risk for pricing or certification claims."
            )
            gaps = [] if len(evidence) >= 2 else ["thin_evidence_for_risk_scoring"]
        else:  # decision
            content = (
                f"## Decision\n"
                f"Decision memo draft for «{query}»:\n{summary}\n\n"
                f"Recommendation: proceed with a shortlist of vendors backed by "
                f"cited primary documentation; defer final selection until Reviewer "
                f"citation gate passes and Decision Memo fields are complete."
            )
            gaps = [] if cite_ids else ["no_citations_available"]

        blocks[specialty] = {
            "specialty": specialty,
            "content": content,
            "gaps": gaps,
            "citation_ids": list(cite_ids),
        }

    return {
        "analysis_results": blocks,
        "events": [
            {
                "type": "analysis.completed",
                "task_id": state.get("task_id", ""),
                "payload": {"specialties": list(blocks.keys())},
                "ts": now,
            }
        ],
        "route": "citation",
    }
