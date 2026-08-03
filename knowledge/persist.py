"""Disk persistence for in-memory knowledge backends (CLI cross-process)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from knowledge.models import DocumentMeta, Entity, Relation
from knowledge.settings import KnowledgeSettings

logger = logging.getLogger("researchos.knowledge.persist")


def state_path(settings: KnowledgeSettings) -> Path:
    return settings.objects_path.parent / "knowledge_state.json"


def save_registry(registry: Any) -> Path:
    """Persist documents, chunk payloads, entities, relations for memory backends."""
    path = state_path(registry.settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    graph = registry.graph
    entities = []
    relations = []
    if hasattr(graph, "entities"):
        entities = [e.model_dump(mode="json") for e in graph.entities.values()]
    if hasattr(graph, "relations"):
        relations = [r.model_dump(mode="json") for r in graph.relations]
    docs = []
    if hasattr(registry.documents, "_docs"):
        docs = [d.model_dump(mode="json") for d in registry.documents._docs.values()]
    payload = {
        "documents": docs,
        "chunk_payloads": registry.chunk_payloads,
        "entities": entities,
        "relations": relations,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    logger.debug("persisted knowledge state -> %s", path)
    return path


def load_registry(registry: Any) -> bool:
    path = state_path(registry.settings)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("failed to load knowledge state: %s", exc)
        return False

    for doc in data.get("documents") or []:
        meta = DocumentMeta.model_validate(doc)
        registry.documents._docs[meta.doc_id] = meta

    payloads = data.get("chunk_payloads") or {}
    registry.chunk_payloads.update(payloads)
    items = list(payloads.values())
    if items:
        try:
            registry.vector.upsert_chunks(items)
        except Exception as exc:  # noqa: BLE001
            logger.warning("vector reload failed: %s", exc)
        for p in items:
            registry.bm25.upsert(p["chunk_id"], p.get("text", ""), p)

    entities = [Entity.model_validate(e) for e in data.get("entities") or []]
    relations = [Relation.model_validate(r) for r in data.get("relations") or []]
    if entities or relations:
        if hasattr(registry.graph, "upsert"):
            registry.graph.upsert(entities, relations)
        else:
            registry.graph.upsert_entities(entities)
            registry.graph.upsert_relations(relations)
    logger.info("loaded knowledge state from %s (%s chunks)", path, len(payloads))
    return True
