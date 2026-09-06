"""Manuscript domain unit tests (stages + release gate; hermetic)."""

from __future__ import annotations

from scientific.manuscript.provenance.record import ProvenanceRecord, SourceRef
from scientific.manuscript.release_gate import run_release_gate
from scientific.manuscript.stages import Stage, allowed_transition, is_terminal, next_stage


def _rec(claim_id: str, *, doi: str | None = None, sourced: bool = True) -> ProvenanceRecord:
    sources = (
        [SourceRef(source_id="doc_1", chunk_ids=["chk_1"], doi=doi)] if sourced else []
    )
    return ProvenanceRecord(
        claim_id=claim_id,
        claim_text="claim",
        created_at="2026-09-06T00:00:00Z",
        sources=sources,
    )


def test_stage_machine() -> None:
    assert next_stage(Stage.OUTLINE) == Stage.EVIDENCE
    assert next_stage(Stage.JOURNALIZE) == Stage.EXPORTED
    assert next_stage(Stage.EXPORTED) is None
    assert allowed_transition(Stage.DRAFTING, Stage.REVIEW)
    assert allowed_transition(Stage.REVIEW, Stage.DRAFTING)  # rework loop
    assert not allowed_transition(Stage.DRAFTING, Stage.OUTLINE)
    assert is_terminal(Stage.EXPORTED) and not is_terminal(Stage.JOURNALIZE)


def test_release_gate_passes() -> None:
    def fake(d: str) -> dict[str, str]:
        return {"doi": d}

    rep = run_release_gate([_rec("c1", doi="10.1234/x")], ai_disclosure=True, scholar_verify=fake)
    assert rep.passed


def test_release_gate_blocks_phantom() -> None:
    def fake(d: str) -> dict[str, int]:
        return {"phantom": 1}

    rep = run_release_gate([_rec("c1", doi="10.1234/x")], ai_disclosure=True, scholar_verify=fake)
    assert not rep.passed
    assert rep.phantom == ["10.1234/x"]


def test_release_gate_blocks_missing_source_and_disclosure() -> None:
    rep = run_release_gate(
        [_rec("c1", sourced=False)],
        ai_disclosure=False,
        scholar_verify=lambda d: {"doi": d},
    )
    assert not rep.passed
    assert rep.unresolved_claims == 1
    assert not rep.has_ai_disclosure
