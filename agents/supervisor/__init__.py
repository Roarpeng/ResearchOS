"""Supervisor Agent — sole routing authority for ResearchOS Runtime."""

from __future__ import annotations

import os
from typing import Any

from runtime.researchos_runtime.events import make_event, new_interrupt_id, node_end, node_start
from runtime.researchos_runtime.state import TaskState, TaskStatus


KNOWN_WORKER_ROUTES = {
    "planner",
    "research",
    "research_stub",
    "etl",
    "analysis",
    "citation",
    "reviewer",
    "writer",
    "memory",
    "plc",
    "human_interrupt",
    "end",
}

# Map plan agent names onto LangGraph node ids
AGENT_TO_NODE = {
    "planner": "planner",
    "research": "research",
    "research_stub": "research",
    "etl": "etl",
    "analysis": "analysis",
    "citation": "citation",
    "reviewer": "reviewer",
    "writer": "writer",
    "memory": "memory",
    "plc": "plc",
    "human_interrupt": "human_interrupt",
    "end": "end",
}


def _auto_approve_enabled() -> bool:
    raw = os.getenv("DEV_AUTO_APPROVE", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _budget_exhausted(state: TaskState) -> bool:
    budgets = state.get("budgets") or {}
    checks = (
        ("used_tool_calls", "max_tool_calls"),
        ("used_tokens", "max_tokens"),
        ("used_web_pages", "max_web_pages"),
    )
    for used_key, max_key in checks:
        used = int(budgets.get(used_key) or 0)
        maximum = int(budgets.get(max_key) or 0)
        if maximum > 0 and used >= maximum:
            return True
    return False


def _plan_steps(state: TaskState) -> list[dict[str, Any]]:
    plan = state.get("plan") or {}
    steps = plan.get("steps") or []
    return list(steps)


def _has_plan(state: TaskState) -> bool:
    return bool(_plan_steps(state))


def _plan_approved(state: TaskState) -> bool:
    plan = state.get("plan") or {}
    return bool(plan.get("approved"))


def _deps_satisfied(step: dict[str, Any], steps_by_id: dict[str, dict[str, Any]]) -> bool:
    for dep in step.get("depends_on") or []:
        dep_step = steps_by_id.get(dep)
        if not dep_step or dep_step.get("status") != "completed":
            return False
    return True


def next_executable_step(state: TaskState) -> dict[str, Any] | None:
    steps = _plan_steps(state)
    by_id = {s.get("id"): s for s in steps if s.get("id")}
    for step in steps:
        if step.get("status", "pending") != "pending":
            continue
        if _deps_satisfied(step, by_id):
            return step
    return None


def decide_route(state: TaskState, *, auto_approve: bool | None = None) -> tuple[str, dict[str, Any]]:
    """Return (route, side_effects) without mutating status for interrupt payload.

    side_effects may include:
      - approve_plan: bool
      - interrupt: InterruptRecord dict
      - status: TaskStatus
      - reason: str
    """
    auto = _auto_approve_enabled() if auto_approve is None else auto_approve
    side: dict[str, Any] = {}

    status = state.get("status")
    if status == TaskStatus.WAITING_HUMAN or status == TaskStatus.WAITING_HUMAN.value:
        side["reason"] = "waiting_human"
        return "human_interrupt", side

    # Unresolved interrupts (append-only: a later resolved twin with same id clears it)
    items = list(state.get("interrupts") or [])
    resolved_ids = {i.get("id") for i in items if i.get("resolved") and i.get("id")}
    unresolved = [
        i for i in items if not i.get("resolved") and i.get("id") not in resolved_ids
    ]
    if unresolved:
        side["reason"] = "unresolved_interrupt"
        return "human_interrupt", side

    if _budget_exhausted(state):
        interrupt = {
            "id": new_interrupt_id(),
            "kind": "budget_exceeded",
            "prompt": "Tool/token budget exhausted. Increase budget or shrink scope?",
            "options": ["increase_budget", "shrink_scope", "deliver_partial", "abort"],
            "resolution": None,
            "resolved": False,
        }
        side["interrupt"] = interrupt
        side["status"] = TaskStatus.WAITING_HUMAN.value
        side["reason"] = "budget_exhausted"
        return "human_interrupt", side

    hops = int((state.get("meta") or {}).get("supervisor_hops") or 0)
    max_hops = int((state.get("meta") or {}).get("max_supervisor_hops") or 32)
    if hops >= max_hops:
        side["status"] = TaskStatus.FAILED.value
        side["reason"] = "max_supervisor_hops"
        return "end", side

    if not _has_plan(state):
        side["reason"] = "no_plan"
        return "planner", side

    if not _plan_approved(state):
        if auto:
            side["approve_plan"] = True
            side["reason"] = "auto_approve"
            # Fall through to next step after approval
        else:
            interrupt = {
                "id": new_interrupt_id(),
                "kind": "plan_approval",
                "prompt": "Approve the research plan?",
                "options": ["approve", "edit", "abort"],
                "resolution": None,
                "resolved": False,
            }
            side["interrupt"] = interrupt
            side["status"] = TaskStatus.WAITING_HUMAN.value
            side["reason"] = "plan_approval"
            return "human_interrupt", side

    # After auto-approve, treat as approved for step selection
    effective = dict(state)
    if side.get("approve_plan"):
        plan = dict(state.get("plan") or {})
        plan["approved"] = True
        effective["plan"] = plan

    step = next_executable_step(effective)  # type: ignore[arg-type]
    if step:
        agent = str(step.get("agent") or "research")
        # Strip specialty suffix e.g. analysis:competitors
        base = agent.split(":", 1)[0]
        route = AGENT_TO_NODE.get(base, "research")
        side["reason"] = f"next_step:{step.get('id')}"
        side["step_id"] = step.get("id")
        side["agent"] = agent
        return route, side

    # All planned steps done — still require a result when writer ran
    if state.get("result"):
        side["reason"] = "done_with_result"
        side["status"] = TaskStatus.COMPLETED.value
        return "end", side

    side["reason"] = "no_pending_steps"
    side["status"] = TaskStatus.COMPLETED.value
    return "end", side


def supervisor_node(state: TaskState) -> dict[str, Any]:
    """LangGraph node: decide next route and emit events."""
    task_id = state.get("task_id") or "unknown"
    updates: dict[str, Any] = {
        "events": [node_start(task_id, "supervisor")],
        "status": TaskStatus.RUNNING.value,
    }

    meta = dict(state.get("meta") or {})
    hops = int(meta.get("supervisor_hops") or 0) + 1
    meta["supervisor_hops"] = hops
    if "max_supervisor_hops" not in meta:
        meta["max_supervisor_hops"] = int(os.getenv("MAX_SUPERVISOR_HOPS", "32"))
    updates["meta"] = meta

    route, side = decide_route(state)

    if side.get("approve_plan"):
        plan = dict(state.get("plan") or {})
        plan["approved"] = True
        updates["plan"] = plan
        # Re-decide after approval so we don't loop on approve forever
        state_after = {**state, "plan": plan, "meta": meta}
        route, side = decide_route(state_after, auto_approve=True)

    if side.get("interrupt"):
        updates["interrupts"] = [side["interrupt"]]
        updates["events"] = updates.get("events", []) + [
            make_event(
                "interrupt",
                task_id,
                {
                    "interrupt_id": side["interrupt"]["id"],
                    "interrupt_type": side["interrupt"]["kind"],
                    "prompt": side["interrupt"]["prompt"],
                    "options": side["interrupt"].get("options") or [],
                },
                agent="supervisor",
            )
        ]

    if side.get("status"):
        updates["status"] = side["status"]

    updates["route"] = route
    updates["events"] = updates.get("events", []) + [
        node_end(
            task_id,
            "supervisor",
            route=route,
            reason=side.get("reason"),
            step_id=side.get("step_id"),
        )
    ]
    return updates


__all__ = [
    "AGENT_TO_NODE",
    "decide_route",
    "next_executable_step",
    "supervisor_node",
]
