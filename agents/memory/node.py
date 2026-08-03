"""Memory Agent: persist research artifacts into Knowledge Layer for evolution."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from runtime.researchos_runtime.state import TaskState

logger = logging.getLogger("researchos.agents.memory")


def _build_memory_document(state: TaskState) -> str:
    """Assemble a Markdown summary from research results for knowledge ingestion."""
    goal = state.get("goal") or {}
    query = goal.get("raw_query") or goal.get("normalized_objective") or "Research"
    result = state.get("result") or ""
    citations = list(state.get("citations") or [])
    analysis = dict(state.get("analysis_results") or {})

    lines: list[str] = [
        f"# Memory: {query[:120]}",
        "",
        f"**Task ID:** {state.get('task_id', 'unknown')}",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Summary",
        "",
    ]

    if result:
        # Strip YAML front-matter if present
        body = result
        if body.startswith("---"):
            end = body.find("---", 3)
            if end != -1:
                body = body[end + 3:].strip()
        lines.append(body[:2000])
    else:
        lines.append("_(No report generated)_")

    if analysis:
        lines.append("")
        lines.append("## Analysis Highlights")
        lines.append("")
        for specialty, block in analysis.items():
            content = str((block or {}).get("content") or "")[:400]
            if content:
                lines.append(f"### {specialty.title()}")
                lines.append(content)
                lines.append("")

    if citations:
        lines.append("## Sources")
        lines.append("")
        for cit in citations[:20]:
            title = cit.get("title") or cit.get("id") or "untitled"
            url = cit.get("url") or ""
            lines.append(f"- {title}: {url}" if url else f"- {title}")

    return "\n".join(lines)


def run(state: TaskState) -> dict[str, Any]:
    analysis = dict(state.get("analysis_results") or {})
    citations = list(state.get("citations") or [])
    evidence = list(state.get("evidence") or [])
    result = state.get("result") or ""

    memory_doc = _build_memory_document(state)
    task_id = state.get("task_id") or "unknown"

    would_persist = {
        "episodic_summary": (result[:400] + "\u2026") if len(result) > 400 else result,
        "semantic_candidates": [
            {
                "specialty": name,
                "citation_ids": list((block or {}).get("citation_ids") or []),
            }
            for name, block in analysis.items()
        ],
        "evidence_count": len(evidence),
        "citation_count": len(citations),
    }

    # Attempt real knowledge ingestion for memory evolution
    ingest_status = "skipped"
    ingest_warnings: list[str] = []
    try:
        from knowledge.pipeline import KnowledgePipeline

        pipeline = KnowledgePipeline()
        ingest_result = pipeline.ingest_text(
            memory_doc,
            filename=f"memory_{task_id}.md",
            title=f"Memory: {task_id}",
        )
        ingest_status = ingest_result.status
        ingest_warnings = ingest_result.warnings
        would_persist["ingested"] = True
        would_persist["ingest_chunks"] = ingest_result.chunk_count
        would_persist["ingest_entities"] = ingest_result.entity_count
        logger.info(
            "memory ingested task_id=%s chunks=%d entities=%d status=%s",
            task_id, ingest_result.chunk_count, ingest_result.entity_count, ingest_status,
        )
    except ImportError:
        ingest_warnings.append("knowledge_pipeline_not_available")
        would_persist["ingested"] = False
        logger.warning("knowledge pipeline not importable; memory stub only")
    except Exception as exc:  # noqa: BLE001
        ingest_warnings.append(f"ingest_failed:{exc}")
        would_persist["ingested"] = False
        logger.exception("memory ingest failed task_id=%s", task_id)

    meta = {
        **(state.get("meta") or {}),
        "memory_write": True,
        "memory_summary": would_persist,
        "memory_ingest_status": ingest_status,
        "memory_warnings": ingest_warnings,
    }
    now = datetime.now(timezone.utc).isoformat()
    return {
        "meta": meta,
        "route": "end",
        "events": [
            {
                "type": "memory.write",
                "task_id": task_id,
                "payload": {
                    "memory_write": True,
                    "ingest_status": ingest_status,
                    "semantic_candidates": len(would_persist["semantic_candidates"]),
                    "chars": len(memory_doc),
                },
                "ts": now,
            }
        ],
    }
