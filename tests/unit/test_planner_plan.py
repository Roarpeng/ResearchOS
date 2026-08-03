"""Unit tests — planner agent."""

from __future__ import annotations

from agents.planner import build_rule_based_plan, plan_from_goal, planner_node
from runtime.researchos_runtime.state import initial_state


def test_rule_based_plan_has_six_steps():
    plan = build_rule_based_plan("对比海康与大华")
    assert plan["approved"] is False
    agents = [s["agent"] for s in plan["steps"]]
    assert agents == [
        "research",
        "analysis",
        "citation",
        "reviewer",
        "writer",
        "memory",
    ]
    assert plan["steps"][0]["depends_on"] == []
    assert plan["steps"][1]["depends_on"] == ["S1"]


def test_planner_node_writes_plan():
    state = initial_state("tp1", "工业机器人市场调研")
    out = planner_node(state)
    assert out["plan"]["steps"]
    assert len(out["plan"]["steps"]) >= 4
    assert out["goal"]["normalized_objective"]
    assert any(e["type"] == "node_end" for e in out["events"])


def test_plan_from_goal_increments_version(monkeypatch):
    monkeypatch.delenv("LITELLM_BASE_URL", raising=False)
    state = initial_state("tp2", "query")
    state["plan"] = {"version": 2, "approved": False, "steps": []}
    plan = plan_from_goal(state)
    assert plan["version"] == 3
