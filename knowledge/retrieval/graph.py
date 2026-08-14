"""Knowledge graph adapter — in-memory default, optional Neo4j."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from knowledge.models import Entity, Relation
from knowledge.settings import KnowledgeSettings, get_settings

logger = logging.getLogger("researchos.knowledge.graph")

_NEO4J_PRIMITIVES = (str, int, float, bool)


def neo4j_safe_properties(props: dict[str, Any] | None) -> dict[str, Any]:
    """Coerce property maps to Neo4j-legal values (primitives or arrays thereof).

    Nested dicts / lists-of-dicts become JSON strings. ``None`` is omitted.
    """
    if not props:
        return {}
    out: dict[str, Any] = {}
    for key, value in props.items():
        if value is None:
            continue
        out[str(key)] = _neo4j_safe_value(value)
    return out


def _neo4j_safe_value(value: Any) -> Any:
    if isinstance(value, _NEO4J_PRIMITIVES):
        return value
    if isinstance(value, Mapping):
        return json.dumps(dict(value), ensure_ascii=False, default=str)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        items = list(value)
        if not items:
            return []
        if all(isinstance(x, _NEO4J_PRIMITIVES) for x in items) and _neo4j_homogeneous(items):
            return items
        return json.dumps(items, ensure_ascii=False, default=str)
    return json.dumps(value, ensure_ascii=False, default=str)


def _neo4j_homogeneous(items: list[Any]) -> bool:
    kinds = {type(x) for x in items}
    return len(kinds) == 1 or kinds <= {int, float}


@dataclass
class GraphHit:
    chunk_id: str
    score: float
    paths: list[dict[str, Any]] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)


class KnowledgeGraph(Protocol):
    def upsert_entities(self, entities: list[Entity]) -> int: ...

    def upsert_relations(self, relations: list[Relation]) -> int: ...

    def query(
        self,
        query: str,
        *,
        template: str | None = None,
        params: dict[str, Any] | None = None,
        top_k: int = 10,
    ) -> dict[str, Any]: ...

    def search_chunks(self, query: str, top_k: int = 10) -> list[GraphHit]: ...


class InMemoryKnowledgeGraph:
    def __init__(self) -> None:
        self.entities: dict[str, Entity] = {}
        self.relations: list[Relation] = []
        self._chunk_links: dict[str, set[str]] = {}

    def clear(self) -> None:
        self.entities.clear()
        self.relations.clear()
        self._chunk_links.clear()

    def upsert_entities(self, entities: list[Entity]) -> int:
        for e in entities:
            existing = self.entities.get(e.canonical_key)
            if existing:
                existing.properties.update(e.properties)
                existing.name = e.name or existing.name
            else:
                self.entities[e.canonical_key] = e
        return len(entities)

    def upsert_relations(self, relations: list[Relation]) -> int:
        n = 0
        for r in relations:
            self.relations.append(r)
            chunk_id = (r.properties or {}).get("chunk_id")
            if chunk_id:
                self._chunk_links.setdefault(str(chunk_id), set()).add(r.from_key)
                self._chunk_links.setdefault(str(chunk_id), set()).add(r.to_key)
            n += 1
        return n

    def upsert(self, entities: list[Entity], relations: list[Relation]) -> dict[str, int]:
        return {
            "entities": self.upsert_entities(entities),
            "relations": self.upsert_relations(relations),
        }

    def query(
        self,
        query: str,
        *,
        template: str | None = None,
        params: dict[str, Any] | None = None,
        top_k: int = 10,
    ) -> dict[str, Any]:
        params = params or {}
        nodes = list(self.entities.values())
        edges = list(self.relations)
        if template == "product_specs":
            product_key = params.get("product_key")
            edges = [
                r
                for r in edges
                if r.type == "HAS_FEATURE" and (not product_key or r.from_key == product_key)
            ]
            keys = {r.from_key for r in edges} | {r.to_key for r in edges}
            nodes = [e for e in nodes if e.canonical_key in keys]
        elif template == "product_compare":
            edges = [r for r in edges if r.type == "COMPARES"]
            keys = {r.from_key for r in edges} | {r.to_key for r in edges}
            nodes = [e for e in nodes if e.canonical_key in keys]
        elif query:
            q = query.lower()
            nodes = [
                e
                for e in nodes
                if q in e.name.lower() or q in e.canonical_key.lower()
            ][:top_k]
            keys = {e.canonical_key for e in nodes}
            edges = [r for r in edges if r.from_key in keys or r.to_key in keys]
        evidence = sorted(
            {
                str(r.properties.get("chunk_id"))
                for r in edges
                if r.properties.get("chunk_id")
            }
        )
        return {
            "nodes": [e.model_dump() for e in nodes[:top_k]],
            "edges": [r.model_dump() for r in edges[: top_k * 2]],
            "evidence_chunk_ids": evidence[:top_k],
        }

    def search_chunks(self, query: str, top_k: int = 10) -> list[GraphHit]:
        q = query.lower()
        tokens = set(re.findall(r"[\w\u4e00-\u9fff]+", q))
        scored: dict[str, float] = {}
        paths: dict[str, list[dict[str, Any]]] = {}
        for key, ent in self.entities.items():
            blob = f"{ent.name} {ent.canonical_key}".lower()
            overlap = sum(1 for t in tokens if t and t in blob)
            if overlap == 0 and q not in blob:
                continue
            score = float(overlap) + (1.0 if q in blob else 0.0)
            for chunk_id, linked in self._chunk_links.items():
                if key in linked:
                    scored[chunk_id] = scored.get(chunk_id, 0.0) + score
                    paths.setdefault(chunk_id, []).append(
                        {"entity": key, "type": ent.type, "name": ent.name}
                    )
        # Also rank by relation mentions of product tokens in query
        for rel in self.relations:
            chunk_id = rel.properties.get("chunk_id")
            if not chunk_id:
                continue
            if any(
                t and (t in rel.from_key.lower() or t in rel.to_key.lower()) for t in tokens
            ):
                scored[str(chunk_id)] = scored.get(str(chunk_id), 0.0) + 0.5
                paths.setdefault(str(chunk_id), []).append(
                    {"relation": rel.type, "from": rel.from_key, "to": rel.to_key}
                )
        ranked = sorted(scored.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [
            GraphHit(chunk_id=cid, score=score, paths=paths.get(cid, []))
            for cid, score in ranked
        ]


class Neo4jKnowledgeGraph:
    def __init__(self, uri: str, user: str, password: str) -> None:
        from neo4j import GraphDatabase

        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self._driver.verify_connectivity()

    def close(self) -> None:
        self._driver.close()

    def upsert_entities(self, entities: list[Entity]) -> int:
        with self._driver.session() as session:
            for e in entities:
                session.run(
                    """
                    MERGE (n:Entity {canonical_key: $key})
                    SET n.type = $type, n.name = $name, n += $props
                    """,
                    key=e.canonical_key,
                    type=e.type,
                    name=e.name,
                    props=neo4j_safe_properties(e.properties),
                )
        return len(entities)

    def upsert_relations(self, relations: list[Relation]) -> int:
        with self._driver.session() as session:
            for r in relations:
                session.run(
                    """
                    MERGE (a:Entity {canonical_key: $from_key})
                    MERGE (b:Entity {canonical_key: $to_key})
                    MERGE (a)-[rel:RELATED {type: $rtype}]->(b)
                    SET rel += $props
                    """,
                    from_key=r.from_key,
                    to_key=r.to_key,
                    rtype=r.type,
                    props=neo4j_safe_properties(r.properties),
                )
        return len(relations)

    def query(
        self,
        query: str,
        *,
        template: str | None = None,
        params: dict[str, Any] | None = None,
        top_k: int = 10,
    ) -> dict[str, Any]:
        params = params or {}
        cypher = """
        MATCH (n:Entity)
        WHERE toLower(n.name) CONTAINS toLower($q)
           OR toLower(n.canonical_key) CONTAINS toLower($q)
        OPTIONAL MATCH (n)-[r:RELATED]->(m)
        RETURN n, collect(r) as rels, collect(m) as ms
        LIMIT $limit
        """
        with self._driver.session() as session:
            result = session.run(cypher, q=query or params.get("product_key", ""), limit=top_k)
            nodes = []
            edges = []
            evidence: list[str] = []
            for record in result:
                n = record["n"]
                nodes.append(
                    {
                        "type": n.get("type"),
                        "canonical_key": n.get("canonical_key"),
                        "name": n.get("name"),
                        "properties": dict(n),
                    }
                )
                for r, m in zip(record["rels"], record["ms"]):
                    if r is None or m is None:
                        continue
                    edges.append(
                        {
                            "type": r.get("type"),
                            "from_key": n.get("canonical_key"),
                            "to_key": m.get("canonical_key"),
                            "properties": dict(r),
                        }
                    )
                    if r.get("chunk_id"):
                        evidence.append(str(r.get("chunk_id")))
        return {
            "nodes": nodes,
            "edges": edges,
            "evidence_chunk_ids": sorted(set(evidence))[:top_k],
        }

    def search_chunks(self, query: str, top_k: int = 10) -> list[GraphHit]:
        data = self.query(query, top_k=top_k)
        hits = []
        for i, cid in enumerate(data.get("evidence_chunk_ids") or []):
            hits.append(GraphHit(chunk_id=cid, score=1.0 / (i + 1), paths=[]))
        return hits


def create_knowledge_graph(settings: KnowledgeSettings | None = None) -> KnowledgeGraph:
    cfg = settings or get_settings()
    if cfg.neo4j_uri and cfg.neo4j_password:
        try:
            kg = Neo4jKnowledgeGraph(cfg.neo4j_uri, cfg.neo4j_user, cfg.neo4j_password)
            logger.info("Using Neo4j at %s", cfg.neo4j_uri)
            return kg
        except Exception as exc:  # noqa: BLE001
            logger.warning("Neo4j unavailable (%s); using in-memory graph", exc)
    return InMemoryKnowledgeGraph()
