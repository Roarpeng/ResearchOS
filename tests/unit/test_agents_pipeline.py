"""Smoke tests for research pipeline agent nodes."""

from __future__ import annotations

from agents.analysis.node import run as analysis_run
from agents.citation.node import run as citation_run
from agents.memory.node import run as memory_run
from agents.registry import get_agent_registry
from agents.research.node import run as research_run
from agents.reviewer.node import run as reviewer_run
from agents.writer.node import run as writer_run
from runtime.researchos_runtime.state import initial_state


def test_registry_contains_phase4_agents():
    reg = get_agent_registry()
    assert set(reg) >= {"research", "analysis", "citation", "reviewer", "writer", "memory"}


def test_pipeline_happy_path_mock_search():
    state = initial_state("tsk_pipe", "对比协作机器人力控与安全认证")
    state["goal"]["priority_specialties"] = ["competitors", "risks", "decision"]

    # Merge helper for Annotated list fields in unit tests
    def merge(base: dict, upd: dict) -> dict:
        out = dict(base)
        for key, value in upd.items():
            if key in ("evidence", "citations", "events", "tool_traces") and isinstance(value, list):
                out[key] = list(out.get(key) or []) + value
            elif key == "analysis_results" and isinstance(value, dict):
                merged = dict(out.get(key) or {})
                merged.update(value)
                out[key] = merged
            elif key == "meta" and isinstance(value, dict):
                out[key] = {**(out.get(key) or {}), **value}
            else:
                out[key] = value
        return out

    state = merge(state, research_run(state))
    assert state["evidence"]

    state = merge(state, analysis_run(state))
    assert "competitors" in state["analysis_results"]

    state = merge(state, citation_run(state))
    assert state["citations"]
    assert all(
        not str(cid).startswith("TMP:")
        for block in state["analysis_results"].values()
        for cid in (block.get("citation_ids") or [])
    )

    rev = reviewer_run(state)
    state = merge(state, rev)
    assert state["review"]["verdict"] == "pass"

    state = merge(state, writer_run(state))
    assert state["result"] and "[^C" in state["result"]

    state = merge(state, memory_run(state))
    assert state["meta"].get("memory_write") is True
