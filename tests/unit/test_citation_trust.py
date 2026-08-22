"""Unit tests: Citation trust_level / publisher / accessed_at enrichment."""

from __future__ import annotations

from agents.citation.node import run as citation_run
from runtime.researchos_runtime.state import initial_state


def _run_with(evidence):
    state = initial_state("tsk_cit", "topic")
    state["evidence"] = evidence
    return citation_run(state)


def test_citation_adds_trust_publisher_accessed_at():
    out = _run_with(
        [
            {
                "id": "ev_1",
                "title": "EPA doc",
                "content": "IP67 rating",
                "url": "https://www.epa.gov/docs/1",
                "meta": {"publisher": "US EPA"},
            }
        ]
    )
    cites = out["citations"]
    assert len(cites) == 1
    c = cites[0]
    assert c["trust_level"] == "high"
    assert c["publisher"] == "US EPA"  # evidence.meta.publisher wins over URL host
    assert c["accessed_at"]  # ISO timestamp present


def test_citation_trust_gov_edu_high():
    out = _run_with(
        [
            {"id": "ev_2", "title": "Uni paper", "content": "study", "url": "https://cs.mit.edu/papers/1"},
        ]
    )
    c = out["citations"][0]
    assert c["trust_level"] == "high"
    assert c["publisher"] == "cs.mit.edu"  # host derived when no meta publisher


def test_citation_trust_official_vendor_high():
    out = _run_with(
        [
            {"id": "ev_3", "title": "Spec", "content": "spec", "url": "https://www.fanuc.com/en/spec"},
        ]
    )
    c = out["citations"][0]
    assert c["trust_level"] == "high"
    assert c["publisher"] == "fanuc.com"


def test_citation_trust_medium_default_and_low_forum():
    out = _run_with(
        [
            {"id": "ev_4", "title": "Vendor", "content": "spec", "url": "https://www.acme-corp.com/spec"},
            {"id": "ev_5", "title": "Forum", "content": "comment", "url": "https://forum.acme-corp.com/t/1"},
        ]
    )
    by_url = {c["url"]: c for c in out["citations"]}
    assert by_url["https://www.acme-corp.com/spec"]["trust_level"] == "medium"
    assert by_url["https://forum.acme-corp.com/t/1"]["trust_level"] == "low"
