"""Unit tests — workflow plan selection + deep_research multi-round extension."""

from __future__ import annotations

from typing import Any

from agents.planner import build_rule_based_plan
from agents.supervisor import plan_deep_research_round
from runtime.researchos_runtime.state import initial_state

DEFAULT_AGENTS = [
    "research",
    "etl",
    "analysis",
    "citation",
    "reviewer",
    "writer",
    "memory",
]

CONTINUOUS_LEARNING_AGENTS = ["etl", "analysis", "memory"]


# --- workflow plan selection -------------------------------------------------


def test_deep_research_is_default_full_chain_with_summary():
    plan = build_rule_based_plan("open-ended research")
    assert [s["agent"] for s in plan["steps"]] == DEFAULT_AGENTS
    assert "deep_research" in plan["summary"]


def test_continuous_learning_is_lightweight_pipeline():
    plan = build_rule_based_plan("subscribe updates", workflow="continuous_learning")
    assert [s["agent"] for s in plan["steps"]] == CONTINUOUS_LEARNING_AGENTS
    assert "writer" not in [s["agent"] for s in plan["steps"]]
    assert "reviewer" not in [s["agent"] for s in plan["steps"]]
    assert "research" not in [s["agent"] for s in plan["steps"]]
    assert "continuous_learning" in plan["summary"]


def test_rss_update_and_incremental_share_continuous_learning_steps():
    for workflow in ("rss_update", "incremental"):
        plan = build_rule_based_plan("feed", workflow=workflow)
        assert [s["agent"] for s in plan["steps"]] == CONTINUOUS_LEARNING_AGENTS


def test_competitive_analysis_maps_to_default_chain():
    plan = build_rule_based_plan("对比海康与大华", workflow="competitive_analysis")
    assert [s["agent"] for s in plan["steps"]] == DEFAULT_AGENTS
    assert "competitive_analysis" in plan["summary"]


# --- deep_research dynamic round extension -----------------------------------


def _deep_research_state(
    *,
    workflow: str = "deep_research",
    round_no: int = 0,
    max_rounds: int | None = 1,
    gaps: list[str] | None = None,
    analysis_done: bool = True,
) -> dict[str, Any]:
    state = initial_state("tw", "open-ended deep research", workflow=workflow)
    plan = build_rule_based_plan("open-ended deep research", workflow="deep_research")
    plan["approved"] = True
    for step in plan["steps"]:
        base = str(step["agent"]).split(":", 1)[0]
        if base in {"research", "etl", "analysis"}:
            step["status"] = "completed" if analysis_done else "pending"
    state["plan"] = plan
    meta: dict[str, Any] = {"deep_research_round": round_no}
    if max_rounds is not None:
        meta["max_research_rounds"] = max_rounds
    state["meta"] = meta
    if gaps is not None:
        state["analysis_results"] = {"risks": {"specialty": "risks", "gaps": list(gaps)}}
    return state


def test_deep_research_inserts_one_directed_round_before_citation():
    state = _deep_research_state(gaps=["thin_evidence_for_risk_scoring"])
    ext = plan_deep_research_round(state)
    assert ext is not None
    new_steps = ext["plan"]["steps"]
    assert [s["id"] for s in new_steps] == ["S1", "S2", "S3", "R1", "S4", "S5", "S6", "S7"]
    assert new_steps[3]["agent"] == "research"
    assert new_steps[3]["depends_on"] == ["S3"]
    # preceding steps keep completed; inserted + subsequent steps reset pending
    assert all(s["status"] == "completed" for s in new_steps[:3])
    assert all(s["status"] == "pending" for s in new_steps[3:])
    assert ext["meta"]["deep_research_round"] == 1


def test_deep_research_round_cap_prevents_more_rounds():
    state = _deep_research_state(round_no=1, gaps=["thin_evidence_for_risk_scoring"])
    assert plan_deep_research_round(state) is None


def test_deep_research_no_high_priority_gap_no_insert():
    state = _deep_research_state(gaps=["no_citations_available"])
    assert plan_deep_research_round(state) is None
    empty = _deep_research_state(gaps=[])
    assert plan_deep_research_round(empty) is None


def test_deep_research_analysis_not_complete_no_insert():
    state = _deep_research_state(gaps=["thin_evidence_for_risk_scoring"], analysis_done=False)
    assert plan_deep_research_round(state) is None


def test_non_deep_research_workflow_no_insert():
    state = _deep_research_state(
        workflow="competitive_analysis", gaps=["thin_evidence_for_risk_scoring"]
    )
    assert plan_deep_research_round(state) is None


def test_deep_research_env_round_budget_defaults(monkeypatch):
    # When meta lacks max_research_rounds, env DEEP_RESEARCH_ROUNDS is the default.
    monkeypatch.setenv("DEEP_RESEARCH_ROUNDS", "0")
    state = _deep_research_state(max_rounds=None, gaps=["thin_evidence_for_risk_scoring"])
    assert plan_deep_research_round(state) is None
    monkeypatch.setenv("DEEP_RESEARCH_ROUNDS", "2")
    state2 = _deep_research_state(max_rounds=None, gaps=["thin_evidence_for_risk_scoring"])
    ext = plan_deep_research_round(state2)
    assert ext is not None
    assert ext["meta"]["deep_research_round"] == 1
