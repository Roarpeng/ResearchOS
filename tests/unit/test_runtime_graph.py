"""Unit tests — runtime graph, events, hello tool."""

from __future__ import annotations

import os

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from runtime.researchos_runtime.events import make_event, node_start
from runtime.researchos_runtime.graph import build_graph
from runtime.researchos_runtime.mcp_client import MCPClient
from runtime.researchos_runtime.settings import RuntimeSettings
from runtime.researchos_runtime.state import TaskStatus, initial_state
from tools.hello.echo import hello_echo


def test_hello_echo_structured_json():
    payload = hello_echo("ping", task_id="t")
    assert payload["ok"] is True
    assert payload["tool"] == "hello.echo"
    assert payload["echo"] == "echo:ping"


def test_mcp_client_inprocess_trace_fields():
    client = MCPClient(RuntimeSettings(mcp_hello_mode="inprocess"))
    result = client.call_tool("hello.echo", {"message": "hi"}, task_id="t1")
    assert result["ok"] is True
    assert result["tool"] == "hello.echo"
    assert "duration_ms" in result
    assert result["result"]["echo"] == "echo:hi"


def test_events_helper_shape():
    ev = make_event("node_start", "t1", {"agent": "supervisor"})
    assert ev["type"] == "node_start"
    assert ev["task_id"] == "t1"
    assert "ts" in ev
    assert node_start("t1", "planner")["payload"]["agent"] == "planner"


def test_graph_runs_to_plan_at_least(monkeypatch):
    monkeypatch.setenv("DEV_AUTO_APPROVE", "true")
    monkeypatch.delenv("LITELLM_BASE_URL", raising=False)
    graph = build_graph(checkpointer=MemorySaver())
    state = initial_state("tg1", "Phase2 graph smoke")
    state["status"] = TaskStatus.RUNNING
    config = {"configurable": {"thread_id": "tg1"}}
    result = graph.invoke(state, config)
    # Should progress past planner with an approved multi-step plan
    assert result.get("plan")
    assert len(result["plan"].get("steps") or []) >= 6
    assert result["plan"]["approved"] is True
    # With auto-approve, full Phase-4 path should complete
    assert result.get("status") == TaskStatus.COMPLETED
    assert any(t.get("tool") == "search.query" for t in (result.get("tool_traces") or []))
    assert result.get("evidence")
    assert result.get("citations")
    assert result.get("result")
    assert (result.get("meta") or {}).get("memory_write") is True
    event_types = {e.get("type") for e in (result.get("events") or [])}
    assert "node_start" in event_types
    assert "final" in event_types


def test_graph_hitl_plan_approval_resume(monkeypatch):
    monkeypatch.setenv("DEV_AUTO_APPROVE", "false")
    monkeypatch.delenv("LITELLM_BASE_URL", raising=False)
    graph = build_graph(checkpointer=MemorySaver())
    state = initial_state("tg2", "needs approval")
    state["status"] = TaskStatus.RUNNING
    config = {"configurable": {"thread_id": "tg2"}}
    result = graph.invoke(state, config)
    assert result.get("__interrupt__") or graph.get_state(config).next
    snap = graph.get_state(config)
    assert snap.values.get("plan")
    assert snap.values["plan"]["approved"] is False
    resumed = graph.invoke(Command(resume={"action": "approve"}), config)
    assert resumed["plan"]["approved"] is True
    # After approve, may complete or still running depending on hop path
    assert resumed.get("status") in {
        TaskStatus.COMPLETED,
        TaskStatus.RUNNING,
        TaskStatus.WAITING_HUMAN,
        TaskStatus.COMPLETED.value,
        TaskStatus.RUNNING.value,
        TaskStatus.WAITING_HUMAN.value,
    }
    assert resumed.get("evidence") or any(
        t.get("tool") == "search.query" for t in (resumed.get("tool_traces") or [])
    )
