"""Knowledge graph MCP — kg.upsert / kg.query."""

from __future__ import annotations

from typing import Any

from knowledge.models import Entity, Relation
from knowledge.store import get_registry
from tools._mcp_compat import create_mcp_server

mcp = create_mcp_server("knowledge-graph")

_ENTITY_WHITELIST = {
    "Product",
    "Feature",
    "Specification",
    "PainPoint",
    "Review",
    "News",
    "Company",
    "Patent",
    "Chunk",
}
_RELATION_WHITELIST = {
    "HAS_FEATURE",
    "COMPARES",
    "REFERENCES",
    "UPDATED_BY",
    "PRODUCED_BY",
    "RELATED",
}


@mcp.tool(name="kg.upsert")
def kg_upsert(
    entities: list[dict[str, Any]] | None = None,
    relations: list[dict[str, Any]] | None = None,
    require_evidence: bool = True,
) -> dict[str, Any]:
    """Upsert entities and relations (idempotent MERGE semantics in-memory/Neo4j)."""
    entities = entities or []
    relations = relations or []
    ents: list[Entity] = []
    for e in entities:
        etype = e.get("type", "Feature")
        if etype not in _ENTITY_WHITELIST:
            return {"ok": False, "error": f"entity_type_not_allowed:{etype}"}
        ents.append(
            Entity(
                type=etype,
                canonical_key=e["canonical_key"],
                name=e.get("name") or e["canonical_key"],
                properties=e.get("properties") or {},
            )
        )
    rels: list[Relation] = []
    for r in relations:
        rtype = r.get("type", "RELATED")
        if rtype not in _RELATION_WHITELIST:
            return {"ok": False, "error": f"relation_type_not_allowed:{rtype}"}
        props = dict(r.get("properties") or {})
        # normalize from/to shapes
        from_key = r.get("from_key")
        to_key = r.get("to_key")
        if not from_key and isinstance(r.get("from"), dict):
            from_key = r["from"].get("canonical_key")
        if not to_key and isinstance(r.get("to"), dict):
            to_key = r["to"].get("canonical_key")
        if require_evidence and rtype != "REFERENCES" and not props.get("chunk_id"):
            return {
                "ok": False,
                "error": "evidence_required",
                "detail": "relation missing chunk_id while require_evidence=true",
            }
        rels.append(
            Relation(
                type=rtype,
                from_key=str(from_key),
                to_key=str(to_key),
                from_type=r.get("from_type"),
                to_type=r.get("to_type"),
                properties=props,
            )
        )
    graph = get_registry().graph
    if hasattr(graph, "upsert"):
        counts = graph.upsert(ents, rels)  # type: ignore[attr-defined]
    else:
        counts = {
            "entities": graph.upsert_entities(ents),
            "relations": graph.upsert_relations(rels),
        }
    return {"ok": True, **counts}


@mcp.tool(name="kg.query")
def kg_query(
    query: str = "",
    template: str | None = None,
    params: dict[str, Any] | None = None,
    top_k: int = 20,
) -> dict[str, Any]:
    """Parameterized graph query (templates or keyword entity match)."""
    return get_registry().graph.query(
        query,
        template=template,
        params=params,
        top_k=top_k,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
