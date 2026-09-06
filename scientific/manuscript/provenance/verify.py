"""Provenance verification: source coverage + phantom-citation scan (via mcp-scholar)."""

from __future__ import annotations

from typing import Any, Callable

from scientific.manuscript.provenance.record import ProvenanceRecord

ScholarVerifyFn = Callable[[str], dict[str, Any]]


def collect_dois(records: list[ProvenanceRecord]) -> list[str]:
    dois: list[str] = []
    for r in records:
        for s in r.sources:
            if s.doi:
                dois.append(s.doi)
    return dois


def verify_citations(
    records: list[ProvenanceRecord],
    scholar_verify: ScholarVerifyFn | None = None,
) -> dict[str, Any]:
    """Return resolved/phantom citation split. scholar_verify injectable for tests."""
    dois = collect_dois(records)
    if not dois:
        return {"total": 0, "resolved": 0, "phantom": 0, "phantom_items": []}

    if scholar_verify is None:
        from tools.scholar.core import verify

        def scholar_verify(d: str) -> dict[str, Any]:  # noqa: F811
            return verify(d)  # type: ignore[return-value]

    phantom: list[str] = []
    for d in dois:
        try:
            out = scholar_verify(d)
        except Exception:  # noqa: BLE001
            phantom.append(d)
            continue
        # scholar.core.verify returns {total,resolved,phantom,...}; accept both shapes.
        if isinstance(out, dict) and out.get("phantom"):
            phantom.append(d)
        elif isinstance(out, dict) and not out.get("doi"):
            phantom.append(d)
    return {
        "total": len(dois),
        "resolved": len(dois) - len(phantom),
        "phantom": len(phantom),
        "phantom_items": phantom,
    }
