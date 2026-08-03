"""Vector store MCP — vector.upsert / vector.search."""

from __future__ import annotations

from typing import Any

from knowledge.embeddings import embed_texts
from knowledge.store import get_registry
from tools._mcp_compat import create_mcp_server

mcp = create_mcp_server("vector-store")


@mcp.tool(name="vector.upsert")
def vector_upsert(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Upsert chunk payloads (server embeds text when vector missing)."""
    reg = get_registry()
    normalized: list[dict[str, Any]] = []
    raw_vectors: list[list[float]] | None = None
    has_vectors = all(isinstance(c.get("vector"), list) for c in chunks) and bool(chunks)
    if has_vectors:
        raw_vectors = [list(map(float, c["vector"])) for c in chunks]
    for c in chunks:
        payload = dict(c)
        payload.setdefault("chunk_id", c.get("chunk_id"))
        payload.setdefault("text", c.get("text", ""))
        payload.setdefault("source_id", c.get("source_id") or c.get("doc_id") or payload["chunk_id"])
        normalized.append(payload)
        reg.chunk_payloads[payload["chunk_id"]] = payload
        # also index BM25 for hybrid consistency when called standalone
        reg.bm25.upsert(payload["chunk_id"], payload.get("text", ""), payload)
    count = reg.vector.upsert_chunks(normalized, vectors=raw_vectors)
    return {"ok": True, "upserted": count}


@mcp.tool(name="vector.search")
def vector_search(
    query: str,
    top_k: int = 10,
    query_vector: list[float] | None = None,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Semantic vector search with citation fields from payload."""
    hits = get_registry().vector.search(
        query=query,
        query_vector=query_vector,
        top_k=top_k,
        filters=filters,
    )
    return {
        "hits": [
            {
                "chunk_id": h.chunk_id,
                "score": h.score,
                "text": h.text,
                "payload": h.payload,
                "citation": {
                    "source_id": h.payload.get("source_id") or h.payload.get("doc_id"),
                    "source": h.payload.get("source_file"),
                    "locator": h.payload.get("locator"),
                },
            }
            for h in hits
        ]
    }


@mcp.tool(name="vector.embed")
def vector_embed(texts: list[str]) -> dict[str, Any]:
    """Debug helper: embed texts (LiteLLM or pseudo)."""
    return {"vectors": embed_texts(texts)}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
