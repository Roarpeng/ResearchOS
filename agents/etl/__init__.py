"""ETL Agent — Ingest → Parse → Index (Graph + Vector) knowledge pipeline worker.

Per docs/agents/03-ETL-Agent.md: consumes evidence gathered by Research,
persists each source into the Knowledge Layer (object store + chunks +
entities + embeddings), and records per-source receipts in ``meta.etl_receipts``
so Analysis / Citation / Writer can reference deep-ingested knowledge.

Idempotent within a task: sources already recorded in receipts are skipped.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any

from runtime.researchos_runtime.events import make_event
from runtime.researchos_runtime.state import TaskState, ToolTrace

logger = logging.getLogger("researchos.agents.etl")

_MAX_SOURCES_PER_RUN = 24
_MAX_CHARS_PER_SOURCE = 200_000


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_id(evidence: dict[str, Any]) -> str:
    return str(
        evidence.get("source_id")
        or evidence.get("id")
        or hashlib.sha1(str(evidence.get("url") or evidence.get("title") or "").encode()).hexdigest()[:12]
    )


def _filename_for(evidence: dict[str, Any]) -> str:
    raw = str(evidence.get("title") or _source_id(evidence) or "source")
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in raw)[:80]
    return f"{safe or 'source'}.md"


def _existing_source_ids(meta: dict[str, Any]) -> set[str]:
    return {
        str(r.get("source_id"))
        for r in (meta.get("etl_receipts") or [])
        if r.get("source_id")
    }


def run(state: TaskState) -> dict[str, Any]:
    task_id = state.get("task_id") or "unknown"
    meta = dict(state.get("meta") or {})
    done_ids = _existing_source_ids(meta)
    workspace_id = meta.get("workspace_id") or None
    evidence = list(state.get("evidence") or [])

    receipts: list[dict[str, Any]] = []
    traces: list[ToolTrace] = []
    ingested = 0
    skipped = 0
    failed = 0

    candidates = [
        item
        for item in evidence
        if (item.get("content") or "").strip() and _source_id(item) not in done_ids
    ][:_MAX_SOURCES_PER_RUN]

    if not candidates:
        meta = {
            **meta,
            "etl_receipts": list(meta.get("etl_receipts") or []),
            "etl_status": "skipped" if evidence else "no_sources",
        }
        return {
            "meta": meta,
            "events": [
                make_event(
                    "etl.skip",
                    task_id,
                    {"reason": "no_new_sources", "evidence_count": len(evidence)},
                )
            ],
        }

    try:
        from knowledge.pipeline import KnowledgePipeline

        pipeline = KnowledgePipeline()
    except Exception as exc:  # noqa: BLE001
        logger.warning("knowledge pipeline unavailable for ETL: %s", exc)
        meta = {**meta, "etl_status": "pipeline_unavailable"}
        return {
            "meta": meta,
            "events": [make_event("etl.error", task_id, {"error": str(exc)})],
        }

    for item in candidates:
        sid = _source_id(item)
        content = str(item.get("content") or "")[:_MAX_CHARS_PER_SOURCE]
        title = str(item.get("title") or sid)[:200]
        started = _now_iso()
        try:
            result = pipeline.ingest_text(
                content,
                filename=_filename_for(item),
                title=title,
                workspace_id=workspace_id,
            )
            receipt = {
                "source_id": sid,
                "doc_id": result.doc_id,
                "status": result.status,
                "chunk_count": result.chunk_count,
                "entity_count": result.entity_count,
                "relation_count": result.relation_count,
                "object_key": result.object_key,
                "parser": result.parser,
                "channels": dict(result.channels),
                "warnings": list(result.warnings),
                "ingested_at": started,
            }
            if result.status in {"ready", "ready_degraded"}:
                ingested += 1
            elif result.status == "failed":
                failed += 1
            receipts.append(receipt)
            traces.append(
                {
                    "tool": "knowledge.ingest_text",
                    "args": {"source_id": sid, "chars": len(content)},
                    "result_summary": f"{result.status} chunks={result.chunk_count} entities={result.entity_count}",
                    "ok": result.status != "failed",
                    "duration_ms": 0,
                }
            )
        except Exception as exc:  # noqa: BLE001
            failed += 1
            receipts.append(
                {
                    "source_id": sid,
                    "status": "failed",
                    "error": str(exc),
                    "ingested_at": started,
                }
            )
            traces.append(
                {
                    "tool": "knowledge.ingest_text",
                    "args": {"source_id": sid},
                    "result_summary": f"failed: {exc}",
                    "ok": False,
                    "duration_ms": 0,
                }
            )
            logger.exception("ETL ingest failed task_id=%s source=%s", task_id, sid)

    # Per docs/agents/03-ETL-Agent.md §8: parser failures stay visible so the
    # Supervisor can route back to Research for a different source.
    parse_failures = [r["source_id"] for r in receipts if r.get("status") == "failed"]
    meta = {
        **meta,
        "etl_receipts": [*list(meta.get("etl_receipts") or []), *receipts],
        "etl_status": "ready" if failed == 0 else ("partial" if ingested else "failed"),
        "etl_parse_failures": parse_failures,
        "etl_counts": {
            "ingested": ingested,
            "skipped_existing": len(done_ids),
            "failed": failed,
        },
    }

    return {
        "meta": meta,
        "tool_traces": traces,
        "events": [
            make_event(
                "etl.indexed",
                task_id,
                {
                    "sources": len(candidates),
                    "ingested": ingested,
                    "failed": failed,
                    "receipts_total": len(meta["etl_receipts"]),
                },
            )
        ],
    }


__all__ = ["run"]
