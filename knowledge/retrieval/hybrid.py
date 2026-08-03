"""Hybrid retrieval: RRF fusion of vector + BM25 + graph channels."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence

from knowledge.models import Citation, ContextPack, Locator, Passage
from knowledge.retrieval.bm25 import BM25Index
from knowledge.retrieval.graph import KnowledgeGraph
from knowledge.retrieval.vector import VectorStore
from knowledge.settings import KnowledgeSettings, get_settings


def reciprocal_rank_fusion(
    ranked_lists: Mapping[str, Sequence[str]],
    *,
    k: int = 60,
    weights: Mapping[str, float] | None = None,
) -> list[tuple[str, float, list[str]]]:
    """RRF over channel -> ordered chunk_id lists.

    Returns list of (chunk_id, fused_score, channels_hit).
    """
    weights = dict(weights or {})
    scores: dict[str, float] = defaultdict(float)
    channels: dict[str, list[str]] = defaultdict(list)
    for channel, ordered in ranked_lists.items():
        w = float(weights.get(channel, 1.0))
        for rank, chunk_id in enumerate(ordered, start=1):
            scores[chunk_id] += w * (1.0 / (k + rank))
            if channel not in channels[chunk_id]:
                channels[chunk_id].append(channel)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [(cid, score, channels[cid]) for cid, score in ranked]


def _locator_from_payload(payload: dict[str, Any]) -> Locator:
    loc = payload.get("locator") or {}
    if isinstance(loc, Locator):
        return loc
    if isinstance(loc, dict):
        return Locator(**{k: v for k, v in loc.items() if k in Locator.model_fields})
    return Locator(
        page=payload.get("page"),
        paragraph=payload.get("paragraph"),
        url=payload.get("url"),
    )


def _citation_from_payload(
    chunk_id: str,
    payload: dict[str, Any],
    score: float,
) -> Citation:
    locator = _locator_from_payload(payload)
    source_id = str(payload.get("source_id") or payload.get("doc_id") or chunk_id)
    source = str(payload.get("source_file") or payload.get("source") or source_id)
    ts = payload.get("timestamp")
    time: datetime | None
    if isinstance(ts, datetime):
        time = ts
    elif isinstance(ts, str) and ts:
        try:
            time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            time = None
    else:
        time = None
    quote = str(payload.get("text") or "")[:240] or None
    return Citation(
        chunk_id=chunk_id,
        source_id=source_id,
        source=source,
        locator=locator,
        time=time,
        score=score,
        section_type=payload.get("section_type"),
        object_key=payload.get("object_key"),
        quote=quote,
    )


class HybridRetriever:
    def __init__(
        self,
        vector: VectorStore,
        bm25: BM25Index,
        graph: KnowledgeGraph,
        *,
        chunk_payloads: dict[str, dict[str, Any]] | None = None,
        settings: KnowledgeSettings | None = None,
    ) -> None:
        self.vector = vector
        self.bm25 = bm25
        self.graph = graph
        self.chunk_payloads = chunk_payloads if chunk_payloads is not None else {}
        self.settings = settings or get_settings()

    def register_payloads(self, payloads: Iterable[dict[str, Any]]) -> None:
        for p in payloads:
            cid = p.get("chunk_id")
            if cid:
                self.chunk_payloads[str(cid)] = p

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 16,
        filters: dict[str, Any] | None = None,
        channel_weights: Mapping[str, float] | None = None,
        include_subgraph: bool = True,
    ) -> ContextPack:
        diagnostics: dict[str, Any] = {
            "channels_failed": [],
            "channel_hits": {},
        }
        ranked: dict[str, list[str]] = {}
        payload_by_id: dict[str, dict[str, Any]] = dict(self.chunk_payloads)

        # Vector
        try:
            v_hits = self.vector.search(query, top_k=max(top_k * 2, 20), filters=filters)
            ranked["vector"] = [h.chunk_id for h in v_hits]
            diagnostics["channel_hits"]["vector"] = len(v_hits)
            for h in v_hits:
                payload_by_id.setdefault(h.chunk_id, h.payload)
                payload_by_id[h.chunk_id].setdefault("text", h.text)
        except Exception as exc:  # noqa: BLE001
            diagnostics["channels_failed"].append({"channel": "vector", "error": str(exc)})

        # BM25
        try:
            b_hits = self.bm25.search(query, top_k=max(top_k * 2, 20))
            ranked["bm25"] = [h.chunk_id for h in b_hits]
            diagnostics["channel_hits"]["bm25"] = len(b_hits)
            for h in b_hits:
                payload_by_id.setdefault(h.chunk_id, h.payload)
                payload_by_id[h.chunk_id].setdefault("text", h.text)
        except Exception as exc:  # noqa: BLE001
            diagnostics["channels_failed"].append({"channel": "bm25", "error": str(exc)})

        # Graph
        try:
            g_hits = self.graph.search_chunks(query, top_k=max(top_k * 2, 20))
            ranked["graph"] = [h.chunk_id for h in g_hits]
            diagnostics["channel_hits"]["graph"] = len(g_hits)
            subgraph = (
                self.graph.query(query, top_k=top_k)
                if include_subgraph
                else {"nodes": [], "edges": [], "evidence_chunk_ids": []}
            )
        except Exception as exc:  # noqa: BLE001
            diagnostics["channels_failed"].append({"channel": "graph", "error": str(exc)})
            subgraph = {"nodes": [], "edges": [], "evidence_chunk_ids": []}

        fused = reciprocal_rank_fusion(
            ranked,
            k=self.settings.rrf_k,
            weights=channel_weights,
        )
        passages: list[Passage] = []
        for chunk_id, score, channels in fused[:top_k]:
            payload = payload_by_id.get(chunk_id, {"chunk_id": chunk_id, "text": ""})
            if filters:
                models = filters.get("models")
                if models:
                    text_blob = str(payload.get("text") or "")
                    payload_models = payload.get("model") or []
                    if not (
                        any(m in payload_models for m in models)
                        or any(m in text_blob for m in models)
                    ):
                        continue
            citation = _citation_from_payload(chunk_id, payload, score)
            passages.append(
                Passage(
                    chunk_id=chunk_id,
                    text=str(payload.get("text") or ""),
                    section_type=payload.get("section_type"),
                    score=score,
                    channels=channels,
                    citation=citation,
                    source_id=citation.source_id,
                    locator=citation.locator,
                )
            )

        diagnostics["rrf_k"] = self.settings.rrf_k
        diagnostics["fused_count"] = len(passages)
        return ContextPack(
            query=query,
            passages=passages,
            subgraph=subgraph if include_subgraph else {"nodes": [], "edges": []},
            diagnostics=diagnostics,
        )
