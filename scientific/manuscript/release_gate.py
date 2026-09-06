"""Release gate: block export unless citations resolve and claims are sourced (ADR-0010)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from scientific.manuscript.provenance.record import ProvenanceRecord
from scientific.manuscript.provenance.verify import verify_citations

ScholarVerifyFn = Callable[[str], dict[str, Any]]


@dataclass
class ReleaseReport:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    phantom: list[str] = field(default_factory=list)
    unresolved_claims: int = 0
    has_ai_disclosure: bool = False


def run_release_gate(
    records: list[ProvenanceRecord],
    *,
    ai_disclosure: bool = False,
    scholar_verify: ScholarVerifyFn | None = None,
) -> ReleaseReport:
    reasons: list[str] = []
    unresolved = 0

    for r in records:
        if not r.has_source():
            unresolved += 1
            reasons.append(f"claim {r.claim_id} has no source")

    citation = verify_citations(records, scholar_verify)
    phantom = list(citation.get("phantom_items") or [])
    if phantom:
        reasons.append(f"{len(phantom)} phantom citation(s)")

    if not ai_disclosure:
        reasons.append("missing AI-use disclosure")

    return ReleaseReport(
        passed=unresolved == 0 and not phantom and ai_disclosure,
        reasons=reasons,
        phantom=phantom,
        unresolved_claims=unresolved,
        has_ai_disclosure=ai_disclosure,
    )
