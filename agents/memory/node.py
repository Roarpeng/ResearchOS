"""Memory Agent stub: record meta.memory_write and persistence summary."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from runtime.researchos_runtime.state import TaskState


def run(state: TaskState) -> dict[str, Any]:
    analysis = dict(state.get("analysis_results") or {})
    citations = list(state.get("citations") or [])
    evidence = list(state.get("evidence") or [])
    result = state.get("result") or ""

    would_persist = {
        "episodic_summary": (result[:400] + "…") if len(result) > 400 else result,
        "semantic_candidates": [
            {
                "specialty": name,
                "citation_ids": list((block or {}).get("citation_ids") or []),
            }
            for name, block in analysis.items()
        ],
        "evidence_count": len(evidence),
        "citation_count": len(citations),
        "note": "MVP stub — no Neo4j/Qdrant writes performed",
    }

    meta = {
        **(state.get("meta") or {}),
        "memory_write": True,
        "memory_summary": would_persist,
    }
    now = datetime.now(timezone.utc).isoformat()
    return {
        "meta": meta,
        "route": "end",
        "events": [
            {
                "type": "memory.stub_write",
                "task_id": state.get("task_id", ""),
                "payload": {
                    "memory_write": True,
                    "semantic_candidates": len(would_persist["semantic_candidates"]),
                },
                "ts": now,
            }
        ],
    }
