"""Minimal repo tool stub — no real VCS integration."""

from __future__ import annotations

from typing import Any


def search_code(query: str, *, limit: int = 5) -> dict[str, Any]:
    return {
        "ok": True,
        "stub": True,
        "query": query,
        "results": [
            {
                "path": "README.md",
                "snippet": f"(stub) No live repo index; query was: {query}",
                "score": 0.1,
            }
        ][:limit],
    }
