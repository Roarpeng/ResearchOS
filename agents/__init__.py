"""Agents package — keep import side-effects minimal for Gateway boot."""

from __future__ import annotations

from typing import Any

__all__ = ["get_agent", "get_agent_registry"]


def __getattr__(name: str) -> Any:
    if name in {"get_agent", "get_agent_registry"}:
        from agents.registry import get_agent, get_agent_registry

        return get_agent if name == "get_agent" else get_agent_registry
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
