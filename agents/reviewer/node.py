"""Reviewer Agent node: citation coverage gate."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from runtime.researchos_runtime.state import TaskState

CLAIMISH = re.compile(
    r"(建议|结论|风险|份额|价格|认证|IP\d+|ISO\s*\d+|推荐|competitors?|risk)",
    re.IGNORECASE,
)


def run(state: TaskState) -> dict[str, Any]:
    evidence = list(state.get("evidence") or [])
    citations = list(state.get("citations") or [])
    analysis = dict(state.get("analysis_results") or {})
    result_md = state.get("result")

    citation_ids = {str(c.get("id")) for c in citations if c.get("id")}
    reasons: list[str] = []
    gaps: list[str] = []
    citation_issues: list[str] = []

    if not evidence:
        reasons.append("evidence is empty")
        gaps.append("missing_evidence")

    if not citations:
        reasons.append("citations are empty")
        gaps.append("missing_citations")
        citation_issues.append("no citations present")

    for specialty, block in analysis.items():
        block = block or {}
        content = str(block.get("content") or "")
        cite_ids = [str(x) for x in (block.get("citation_ids") or [])]
        looks_like_claim = bool(CLAIMISH.search(content)) or len(content) > 40

        if looks_like_claim and not cite_ids:
            reasons.append(f"analysis.{specialty} lacks citation_ids")
            gaps.append("missing_citations")
            citation_issues.append(f"analysis_results.{specialty}")
            continue

        for cid in cite_ids:
            if cid.startswith("TMP:"):
                citation_issues.append(f"{specialty}:{cid} not normalized")
                reasons.append(f"unnormalized citation ref in {specialty}")
                gaps.append("invalid_citation_id")
            elif cid not in citation_ids:
                citation_issues.append(f"{specialty}:{cid} missing from citations[]")
                reasons.append(f"unknown citation id {cid} in {specialty}")
                gaps.append("invalid_citation_id")

    if result_md:
        markers = re.findall(r"\[\^([^\]]+)\]|\[citation:([^\]]+)\]|\(\[(C\d+)\]\)", result_md)
        flat = [m for group in markers for m in group if m]
        for mid in flat:
            if mid not in citation_ids:
                citation_issues.append(f"result marker {mid} unresolved")
                gaps.append("invalid_citation_id")
                reasons.append(f"unresolved marker {mid} in result")

    verdict = "pass" if not reasons else "reject"
    review = {
        "verdict": verdict,
        "reasons": reasons,
        "gaps": list(dict.fromkeys(gaps)),
        "citation_issues": citation_issues,
    }

    now = datetime.now(timezone.utc).isoformat()
    return {
        "review": review,
        "route": "writer" if verdict == "pass" else "research",
        "events": [
            {
                "type": "review.completed",
                "task_id": state.get("task_id", ""),
                "payload": {"verdict": verdict, "gaps": review["gaps"]},
                "ts": now,
            }
        ],
    }
