"""Vector store adapter — in-memory default, optional Qdrant."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

from knowledge.embeddings import cosine, embed_query, embed_texts
from knowledge.settings import KnowledgeSettings, get_settings

logger = logging.getLogger("researchos.knowledge.vector")


@dataclass
class VectorHit:
    chunk_id: str
    score: float
    text: str
    payload: dict[str, Any] = field(default_factory=dict)
    vector: list[float] | None = None


class VectorStore(Protocol):
    def upsert(
        self,
        chunk_id: str,
        vector: Sequence[float],
        payload: dict[str, Any],
    ) -> None: ...

    def upsert_chunks(
        self,
        chunks: Sequence[dict[str, Any]],
        vectors: Sequence[Sequence[float]] | None = None,
    ) -> int: ...

    def search(
        self,
        query: str | None = None,
        *,
        query_vector: Sequence[float] | None = None,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorHit]: ...

    def delete(self, chunk_id: str) -> None: ...


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._points: dict[str, dict[str, Any]] = {}

    def __len__(self) -> int:
        return len(self._points)

    def clear(self) -> None:
        self._points.clear()

    def upsert(
        self,
        chunk_id: str,
        vector: Sequence[float],
        payload: dict[str, Any],
    ) -> None:
        self._points[chunk_id] = {
            "vector": list(vector),
            "payload": dict(payload),
            "text": payload.get("text", ""),
        }

    def upsert_chunks(
        self,
        chunks: Sequence[dict[str, Any]],
        vectors: Sequence[Sequence[float]] | None = None,
    ) -> int:
        if vectors is None:
            texts = [c.get("text", "") for c in chunks]
            vectors = embed_texts(texts)
        for chunk, vec in zip(chunks, vectors):
            chunk_id = chunk["chunk_id"]
            self.upsert(chunk_id, vec, chunk)
        return len(chunks)

    def delete(self, chunk_id: str) -> None:
        self._points.pop(chunk_id, None)

    def search(
        self,
        query: str | None = None,
        *,
        query_vector: Sequence[float] | None = None,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        if query_vector is None:
            if not query:
                return []
            query_vector = embed_query(query)
        hits: list[VectorHit] = []
        for chunk_id, point in self._points.items():
            payload = point["payload"]
            if filters and not _payload_matches(payload, filters):
                continue
            score = cosine(query_vector, point["vector"])
            hits.append(
                VectorHit(
                    chunk_id=chunk_id,
                    score=score,
                    text=point.get("text") or payload.get("text", ""),
                    payload=payload,
                    vector=point["vector"],
                )
            )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]


def _payload_matches(payload: dict[str, Any], filters: dict[str, Any]) -> bool:
    models = filters.get("models")
    if models:
        payload_models = payload.get("model") or []
        if not any(m in payload_models for m in models):
            # also allow substring match in text/source
            blob = " ".join(
                [
                    str(payload.get("text") or ""),
                    str(payload.get("source_file") or ""),
                    " ".join(payload_models),
                ]
            )
            if not any(m in blob for m in models):
                return False
    source_files = filters.get("source_files")
    if source_files and payload.get("source_file") not in source_files:
        return False
    section_types = filters.get("section_types")
    if section_types and payload.get("section_type") not in section_types:
        return False
    return True


class QdrantVectorStore:
    """Thin Qdrant adapter; falls back behavior left to factory."""

    def __init__(
        self,
        url: str,
        collection: str,
        dim: int,
        api_key: str | None = None,
    ) -> None:
        from qdrant_client import QdrantClient
        from qdrant_client.http import models as qm

        self._qm = qm
        self._client = QdrantClient(url=url, api_key=api_key, timeout=5)
        self.collection = collection
        self.dim = dim
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        from qdrant_client.http import models as qm

        names = {c.name for c in self._client.get_collections().collections}
        if self.collection not in names:
            self._client.create_collection(
                collection_name=self.collection,
                vectors_config=qm.VectorParams(size=self.dim, distance=qm.Distance.COSINE),
            )

    def upsert(
        self,
        chunk_id: str,
        vector: Sequence[float],
        payload: dict[str, Any],
    ) -> None:
        from qdrant_client.http import models as qm

        self._client.upsert(
            collection_name=self.collection,
            points=[
                qm.PointStruct(
                    id=abs(hash(chunk_id)) % (2**63 - 1),
                    vector=list(vector),
                    payload={**payload, "chunk_id": chunk_id},
                )
            ],
        )

    def upsert_chunks(
        self,
        chunks: Sequence[dict[str, Any]],
        vectors: Sequence[Sequence[float]] | None = None,
    ) -> int:
        if vectors is None:
            vectors = embed_texts([c.get("text", "") for c in chunks])
        for chunk, vec in zip(chunks, vectors):
            self.upsert(chunk["chunk_id"], vec, chunk)
        return len(chunks)

    def delete(self, chunk_id: str) -> None:
        from qdrant_client.http import models as qm

        self._client.delete(
            collection_name=self.collection,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[
                        qm.FieldCondition(
                            key="chunk_id",
                            match=qm.MatchValue(value=chunk_id),
                        )
                    ]
                )
            ),
        )

    def search(
        self,
        query: str | None = None,
        *,
        query_vector: Sequence[float] | None = None,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        if query_vector is None:
            if not query:
                return []
            query_vector = embed_query(query)
        results = self._client.search(
            collection_name=self.collection,
            query_vector=list(query_vector),
            limit=top_k,
        )
        hits: list[VectorHit] = []
        for r in results:
            payload = dict(r.payload or {})
            if filters and not _payload_matches(payload, filters):
                continue
            hits.append(
                VectorHit(
                    chunk_id=str(payload.get("chunk_id") or r.id),
                    score=float(r.score or 0.0),
                    text=str(payload.get("text") or ""),
                    payload=payload,
                )
            )
        return hits


def create_vector_store(settings: KnowledgeSettings | None = None) -> VectorStore:
    cfg = settings or get_settings()
    if cfg.qdrant_url:
        try:
            store = QdrantVectorStore(
                url=cfg.qdrant_url,
                collection=cfg.qdrant_collection,
                dim=cfg.embedding_dim,
                api_key=cfg.qdrant_api_key,
            )
            logger.info("Using Qdrant vector store at %s", cfg.qdrant_url)
            return store
        except Exception as exc:  # noqa: BLE001
            logger.warning("Qdrant unavailable (%s); using in-memory vector store", exc)
    return InMemoryVectorStore()
