"""Knowledge facade MCP — knowledge.retrieve / fulltext.search / knowledge.ingest_status.

Per docs/mcp/05-knowledge-tools.md: Research/Writer agents should prefer the
``knowledge.retrieve`` facade (Graph + Vector + BM25 fused Context Bundle)
over channel-specific tools.
"""

from __future__ import annotations

from typing import Any

from knowledge.pipeline import KnowledgePipeline
from knowledge.store import get_registry
from tools._mcp_compat import create_mcp_server

mcp = create_mcp_server("knowledge")


@mcp.tool(name="knowledge.retrieve")
def knowledge_retrieve(
    query: str,
    top_k: int = 8,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fused Graph + Vector + BM25 retrieval with citation provenance."""
    if not (query or "").strip():
        return {"ok": False, "error": "invalid_argument", "detail": "query is empty"}
    try:
        pack = KnowledgePipeline().search(query, top_k=max(1, min(int(top_k), 64)), filters=filters)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "retrieve_failed", "detail": str(exc)}
    return {"ok": True, **pack}


@mcp.tool(name="fulltext.search")
def fulltext_search(
    query: str,
    top_k: int = 10,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Direct BM25 channel search (debug / literal recall boost)."""
    reg = get_registry()
    k = max(1, min(int(top_k), 64))
    try:
        hits = reg.bm25.search(query=query, top_k=k, filters=filters)
    except TypeError:
        # BM25 backend without filter support yet
        hits = reg.bm25.search(query=query, top_k=k)
    return {
        "hits": [
            {
                "chunk_id": getattr(h, "chunk_id", None),
                "score": getattr(h, "score", 0.0),
                "text": getattr(h, "text", ""),
                "payload": getattr(h, "payload", {}) or {},
            }
            for h in hits
        ]
    }


@mcp.tool(name="knowledge.ingest_status")
def knowledge_ingest_status(doc_id: str | None = None) -> dict[str, Any]:
    """Ingest state machine status per document with channel flags."""
    reg = get_registry()
    if doc_id:
        meta = reg.documents.get(doc_id)
        if meta is None:
            return {"ok": False, "error": "not_found", "doc_id": doc_id}
        return {"ok": True, "documents": [meta.model_dump(mode="json")]}
    docs = reg.documents.list()
    return {
        "ok": True,
        "count": len(docs),
        "documents": [d.model_dump(mode="json") for d in docs],
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
