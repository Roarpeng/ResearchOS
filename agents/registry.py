"""Agent name → callable registry for LangGraph wiring."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from runtime.researchos_runtime.state import TaskState

AgentFn = Callable[[TaskState], dict[str, Any]]


def get_agent_registry() -> dict[str, AgentFn]:
    from agents.analysis.node import run as analysis_run
    from agents.citation.node import run as citation_run
    from agents.etl import run as etl_run
    from agents.memory.node import run as memory_run
    from agents.plc.node import run as plc_run
    from agents.research.node import run as research_run
    from agents.reviewer.node import run as reviewer_run
    from agents.writer.node import run as writer_run

    return {
        "research": research_run,
        "etl": etl_run,
        "analysis": analysis_run,
        "citation": citation_run,
        "reviewer": reviewer_run,
        "writer": writer_run,
        "memory": memory_run,
        "plc": plc_run,
    }


def get_agent(name: str) -> AgentFn:
    registry = get_agent_registry()
    if name not in registry:
        raise KeyError(f"unknown agent: {name}; known={sorted(registry)}")
    return registry[name]
