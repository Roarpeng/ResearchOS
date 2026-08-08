"""Gateway facade over KnowledgePipeline: ingest, recall, graph stats, rebuild."""

from __future__ import annotations

import logging
from typing import Any

from gateway.app.services import store as mem

logger = logging.getLogger("researchos.gateway.knowledge_svc")


def _pipeline():
    from knowledge.pipeline import KnowledgePipeline

    return KnowledgePipeline()


def _registry():
    from knowledge.store import get_registry

    return get_registry()


def ingest_document(
    *,
    space_id: str,
    data: bytes,
    filename: str | None,
    mime_type: str | None = None,
    title: str | None = None,
    doc_id: str | None = None,
) -> dict[str, Any]:
    """Parse → chunk → embed → BM25 → graph upsert, scoped to knowledge space id."""
    pipeline = _pipeline()
    result = pipeline.ingest_bytes(
        data,
        filename=filename,
        mime_type=mime_type,
        workspace_id=space_id,
        title=title or filename,
        doc_id=doc_id,
    )
    return {
        "doc_id": result.doc_id,
        "status": result.status,
        "chunk_count": result.chunk_count,
        "entity_count": result.entity_count,
        "relation_count": getattr(result, "relation_count", 0) or 0,
        "parser": result.parser,
        "channels": result.channels,
        "warnings": result.warnings,
        "object_key": result.object_key,
    }


def recall(
    query: str,
    *,
    knowledge_space_ids: list[str] | None = None,
    top_k: int = 6,
) -> dict[str, Any]:
    """Hybrid GraphRAG recall for chat / research replies."""
    filters: dict[str, Any] | None = None
    if knowledge_space_ids:
        filters = {"knowledge_space_ids": knowledge_space_ids}
    pack = _pipeline().search(query, top_k=top_k, filters=filters)
    passages = pack.get("passages") or []
    subgraph = pack.get("subgraph") or {}
    return {
        "query": query,
        "passages": passages,
        "subgraph": subgraph,
        "diagnostics": pack.get("diagnostics") or {},
        "citation_block": format_recall_markdown(passages, subgraph),
    }


def format_recall_markdown(passages: list[dict], subgraph: dict | None = None) -> str:
    if not passages and not (subgraph or {}).get("nodes"):
        return ""
    lines = ["### 知识库召回", ""]
    for i, p in enumerate(passages[:8], 1):
        cit = p.get("citation") or {}
        src = cit.get("source") or p.get("source_id") or "doc"
        score = p.get("score")
        score_s = f"{float(score):.3f}" if isinstance(score, (int, float)) else "?"
        text = str(p.get("text") or "").strip().replace("\n", " ")
        if len(text) > 280:
            text = text[:277] + "…"
        channels = ",".join(p.get("channels") or []) or "hybrid"
        lines.append(f"{i}. [{src}] (score={score_s}, {channels})")
        lines.append(f"   {text}")
    nodes = (subgraph or {}).get("nodes") or []
    if nodes:
        lines.append("")
        lines.append("图谱实体：" + "、".join(
            str(n.get("name") or n.get("canonical_key") or "?") for n in nodes[:12]
        ))
    return "\n".join(lines)


def space_stats(space_id: str | None = None) -> dict[str, Any]:
    reg = _registry()
    docs = reg.documents.list(workspace_id=space_id) if space_id else reg.documents.list()
    chunks = [
        p
        for p in (reg.chunk_payloads or {}).values()
        if not space_id or str(p.get("workspace_id") or "") == space_id
    ]
    graph = reg.graph
    entities_map = getattr(graph, "entities", None)
    if isinstance(entities_map, dict):
        entities = list(entities_map.values())
    else:
        entities = []
    relations_raw = getattr(graph, "relations", None)
    relations = list(relations_raw) if isinstance(relations_raw, list) else []
    return {
        "space_id": space_id,
        "document_count": len(docs),
        "chunk_count": len(chunks),
        "entity_count": len(entities),
        "relation_count": len(relations),
        "documents": [
            {
                "id": d.doc_id,
                "title": d.title,
                "filename": d.source_file,
                "status": d.status,
                "workspace_id": d.workspace_id,
            }
            for d in docs[:100]
        ],
        "channels": {
            "vector": True,
            "bm25": len(reg.bm25) > 0,
            "graph": len(entities) > 0,
        },
    }


def graph_snapshot(space_id: str | None = None, *, limit: int = 40) -> dict[str, Any]:
    reg = _registry()
    graph = reg.graph
    result = graph.query("", top_k=limit) if hasattr(graph, "query") else {"nodes": [], "edges": []}
    if not result.get("nodes") and hasattr(graph, "entities"):
        nodes = [e.model_dump(mode="json") for e in list(graph.entities.values())[:limit]]
        edges = [
            r.model_dump(mode="json") if hasattr(r, "model_dump") else dict(r)
            for r in list(getattr(graph, "relations", []) or [])[: limit * 2]
        ]
        return {"nodes": nodes, "edges": edges, "space_id": space_id}
    return {**result, "space_id": space_id}


def rebuild_indexes(*, space_id: str | None = None) -> dict[str, Any]:
    """Re-upsert BM25/vector/graph from persisted chunk payloads (soft rebuild)."""
    from knowledge.persist import save_registry

    reg = _registry()
    payloads = [
        p
        for p in (reg.chunk_payloads or {}).values()
        if not space_id or str(p.get("workspace_id") or "") == space_id
    ]
    warnings: list[str] = []
    channels = {"vector": False, "bm25": False, "graph": False}
    try:
        if payloads:
            reg.vector.upsert_chunks(payloads)
            channels["vector"] = True
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"vector:{exc}")
    try:
        for p in payloads:
            reg.bm25.upsert(p["chunk_id"], p.get("text", ""), p)
        channels["bm25"] = True
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"bm25:{exc}")
    try:
        save_registry(reg)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"persist:{exc}")
    return {
        "ok": True,
        "chunk_count": len(payloads),
        "channels": channels,
        "warnings": warnings,
        "space_id": space_id,
    }


def active_space_ids() -> list[str]:
    return list(mem.store.spaces.keys())
