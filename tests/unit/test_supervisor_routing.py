"""Unit tests — supervisor routing."""

from __future__ import annotations

import os

from agents.supervisor import decide_route, next_executable_step, supervisor_node
from runtime.researchos_runtime.state import TaskStatus, initial_state


def test_no_plan_routes_to_planner():
    state = initial_state("t1", "研究工业视觉")
    route, side = decide_route(state, auto_approve=False)
    assert route == "planner"
    assert side["reason"] == "no_plan"


def test_unapproved_plan_routes_to_hitl():
    state = initial_state("t2", "goal")
    state["plan"] = {
        "version": 1,
        "approved": False,
        "steps": [
            {
                "id": "S1",
                "title": "Research",
                "agent": "research",
                "status": "pending",
                "depends_on": [],
            }
        ],
    }
    route, side = decide_route(state, auto_approve=False)
    assert route == "human_interrupt"
    assert side["interrupt"]["kind"] == "plan_approval"


def test_auto_approve_then_next_step(monkeypatch):
    monkeypatch.setenv("DEV_AUTO_APPROVE", "true")
    state = initial_state("t3", "goal")
    state["plan"] = {
        "version": 1,
        "approved": False,
        "steps": [
            {
                "id": "S1",
                "title": "Research",
                "agent": "research",
                "status": "pending",
                "depends_on": [],
            }
        ],
    }
    # decide_route with auto_approve only sets approve_plan; supervisor_node re-decides
    route, side = decide_route(state, auto_approve=True)
    assert side.get("approve_plan") is True

    out = supervisor_node(state)
    assert out["plan"]["approved"] is True
    assert out["route"] == "research"


def test_next_pending_step_respects_deps():
    state = initial_state("t4", "goal")
    state["plan"] = {
        "version": 1,
        "approved": True,
        "steps": [
            {
                "id": "S1",
                "title": "Research",
                "agent": "research",
                "status": "completed",
                "depends_on": [],
            },
            {
                "id": "S2",
                "title": "Analysis",
                "agent": "analysis",
                "status": "pending",
                "depends_on": ["S1"],
            },
        ],
    }
    step = next_executable_step(state)
    assert step is not None
    assert step["id"] == "S2"
    route, _ = decide_route(state, auto_approve=True)
    assert route == "analysis"


def test_budget_exhausted_interrupt(monkeypatch):
    monkeypatch.delenv("DEV_AUTO_APPROVE", raising=False)
    state = initial_state("t5", "goal")
    state["plan"] = {
        "version": 1,
        "approved": True,
        "steps": [
            {
                "id": "S1",
                "title": "Research",
                "agent": "research",
                "status": "pending",
                "depends_on": [],
            }
        ],
    }
    state["budgets"] = {
        "max_tool_calls": 1,
        "used_tool_calls": 1,
        "max_tokens": 100,
        "used_tokens": 0,
        "max_web_pages": 10,
        "used_web_pages": 0,
    }
    route, side = decide_route(state, auto_approve=True)
    assert route == "human_interrupt"
    assert side["interrupt"]["kind"] == "budget_exceeded"


def test_all_steps_done_routes_end():
    state = initial_state("t6", "goal")
    state["plan"] = {
        "version": 1,
        "approved": True,
        "steps": [
            {
                "id": "S1",
                "title": "Research",
                "agent": "research",
                "status": "completed",
                "depends_on": [],
            }
        ],
    }
    state["result"] = "# done"
    route, side = decide_route(state, auto_approve=True)
    assert route == "end"
    assert side.get("status") == TaskStatus.COMPLETED


def test_dev_auto_approve_env(monkeypatch):
    monkeypatch.setenv("DEV_AUTO_APPROVE", "true")
    state = initial_state("t7", "goal")
    state["plan"] = {
        "version": 1,
        "approved": False,
        "steps": [
            {
                "id": "S1",
                "title": "Research",
                "agent": "research",
                "status": "pending",
                "depends_on": [],
            }
        ],
    }
    out = supervisor_node(state)
    assert out["route"] == "research"
    assert out["plan"]["approved"] is True
