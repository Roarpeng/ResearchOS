"""Process-wide store registry so CLI / MCP / pipeline share backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from knowledge.documents import DocumentRegistry
from knowledge.retrieval.bm25 import BM25Index
from knowledge.retrieval.graph import KnowledgeGraph, create_knowledge_graph
from knowledge.retrieval.hybrid import HybridRetriever
from knowledge.retrieval.vector import VectorStore, create_vector_store
from knowledge.settings import KnowledgeSettings, get_settings


@dataclass
class StoreRegistry:
    settings: KnowledgeSettings
    documents: DocumentRegistry
    vector: VectorStore
    bm25: BM25Index
    graph: KnowledgeGraph
    chunk_payloads: dict[str, dict[str, Any]] = field(default_factory=dict)

    def hybrid(self) -> HybridRetriever:
        return HybridRetriever(
            self.vector,
            self.bm25,
            self.graph,
            chunk_payloads=self.chunk_payloads,
            settings=self.settings,
        )

    def reset_memory(self) -> None:
        """Clear in-memory backends (tests)."""
        self.documents.clear()
        self.chunk_payloads.clear()
        if hasattr(self.vector, "clear"):
            self.vector.clear()  # type: ignore[attr-defined]
        self.bm25.clear()
        if hasattr(self.graph, "clear"):
            self.graph.clear()  # type: ignore[attr-defined]


@lru_cache
def get_registry() -> StoreRegistry:
    settings = get_settings()
    registry = StoreRegistry(
        settings=settings,
        documents=DocumentRegistry(settings),
        vector=create_vector_store(settings),
        bm25=BM25Index(),
        graph=create_knowledge_graph(settings),
    )
    from knowledge.persist import load_registry

    load_registry(registry)
    return registry


def reset_registry() -> StoreRegistry:
    get_registry.cache_clear()
    return get_registry()
