"""ETL Agent tests — Ingest → Parse → Index with receipts and idempotency."""

from __future__ import annotations

from typing import Any

from agents.etl import run as etl_run
from agents.planner import build_rule_based_plan
from agents.registry import get_agent_registry
from agents.supervisor import AGENT_TO_NODE, decide_route
from runtime.researchos_runtime.state import initial_state


def _evidence(sid: str, content: str) -> dict[str, Any]:
    return {
        "id": f"ev_{sid}",
        "source_id": sid,
        "title": f"Source {sid}",
        "content": content,
        "url": f"https://example.com/{sid}",
    }


def _merge(base: dict, upd: dict) -> dict:
    out = dict(base)
    for key, value in upd.items():
        if key in ("evidence", "citations", "events", "tool_traces") and isinstance(value, list):
            out[key] = list(out.get(key) or []) + value
        elif key == "meta" and isinstance(value, dict):
            out[key] = {**(out.get(key) or {}), **value}
        else:
            out[key] = value
    return out


def test_registry_contains_etl() -> None:
    assert "etl" in get_agent_registry()
    assert AGENT_TO_NODE.get("etl") == "etl"


def test_plan_inserts_etl_after_research() -> None:
    plan = build_rule_based_plan("demo goal")
    agents = [s["agent"] for s in plan["steps"]]
    assert agents.index("etl") == agents.index("research") + 1
    industrial = build_rule_based_plan("plc goal", workflow="industrial")
    ind_agents = [s["agent"] for s in industrial["steps"]]
    assert ind_agents[:3] == ["research", "etl", "plc"]


def test_supervisor_routes_etl_step() -> None:
    state = initial_state("tsk_etl_route", "goal")
    plan = build_rule_based_plan("goal")
    plan["approved"] = True
    # research done → next executable step is etl
    plan["steps"][0]["status"] = "completed"
    state["plan"] = plan
    route, side = decide_route(state, auto_approve=True)
    assert route == "etl"
    assert side.get("step_id") == "S2"


def test_etl_ingests_evidence_and_writes_receipts() -> None:
    state = initial_state("tsk_etl_1", "collaborative robot force control")
    state["evidence"] = [
        _evidence("s1", "# Robot safety\nISO/TS 15066 requires force limits."),
        _evidence("s2", "Vendor B publishes 12 kg payload cobot."),
    ]
    upd = etl_run(state)
    meta = upd["meta"]
    receipts = meta["etl_receipts"]
    assert len(receipts) == 2
    statuses = {r["source_id"]: r["status"] for r in receipts}
    assert set(statuses.values()) <= {"ready", "ready_degraded"}
    assert meta["etl_status"] in {"ready", "partial"}
    assert meta["etl_counts"]["ingested"] == 2
    assert upd["tool_traces"] and all(t["ok"] for t in upd["tool_traces"])
    assert upd["events"] and upd["events"][0]["type"] == "etl.indexed"

    merged = _merge(state, upd)

    # Second run: same sources must be skipped (task-level idempotency)
    upd2 = etl_run(merged)
    assert upd2["events"][0]["type"] == "etl.skip"
    assert len(upd2["meta"]["etl_receipts"]) == 2


def test_etl_without_sources_is_noop() -> None:
    state = initial_state("tsk_etl_empty", "goal without evidence")
    upd = etl_run(state)
    assert upd["meta"]["etl_status"] in {"no_sources", "skipped"}
    assert upd["events"][0]["type"] == "etl.skip"


def test_etl_failure_keeps_receipt_visible() -> None:
    """A source that fails to ingest still produces a failed receipt."""
    state = initial_state("tsk_etl_fail", "goal")
    bad = _evidence("bad", "content")
    state["evidence"] = [bad]
    import unittest.mock as mock

    with mock.patch("knowledge.pipeline.KnowledgePipeline.ingest_text", side_effect=RuntimeError("boom")):
        upd = etl_run(state)
    receipts = upd["meta"]["etl_receipts"]
    assert receipts and receipts[0]["status"] == "failed"
    assert "boom" in (receipts[0].get("error") or "")
    assert upd["meta"]["etl_status"] == "failed"
    assert upd["tool_traces"][0]["ok"] is False