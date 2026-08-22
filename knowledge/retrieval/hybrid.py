"""Hybrid retrieval: RRF fusion of vector + BM25 + graph channels.

Pre-hooks (query understanding + HyDE) run before the channels; the RRF main
path is unchanged. Metadata filters and the recency window are applied
uniformly across all three channels and again at the fusion stage.
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from knowledge.embeddings import embed_texts
from knowledge.models import Citation, ContextPack, Locator, Passage
from knowledge.retrieval.bm25 import BM25Index
from knowledge.retrieval.filters import payload_matches_filters, within_recency_window
from knowledge.retrieval.graph import KnowledgeGraph
from knowledge.retrieval.hyde import _generate as _generate_hyde
from knowledge.retrieval.hyde import is_hyde_enabled
from knowledge.retrieval.query_understanding import QueryUnderstanding, understand_query
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


def _passage_matches_filters(payload: dict[str, Any], filters: dict[str, Any]) -> bool:
    """Back-compat alias for the unified metadata-filter matcher."""
    return payload_matches_filters(payload, filters)


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


def _normalize(vec: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class HybridRetriever:
    def __init__(
        self,
        vector: VectorStore,
        bm25: BM25Index,
        graph: KnowledgeGraph,
        *,
        chunk_payloads: dict[str, dict[str, Any]] | None = None,
        settings: KnowledgeSettings | None = None,
        hyde_enabled: bool | None = None,
        enable_query_understanding: bool = True,
    ) -> None:
        self.vector = vector
        self.bm25 = bm25
        self.graph = graph
        self.chunk_payloads = chunk_payloads if chunk_payloads is not None else {}
        self.settings = settings or get_settings()
        self.hyde_enabled = hyde_enabled
        self.enable_query_understanding = enable_query_understanding

    def register_payloads(self, payloads: Iterable[dict[str, Any]]) -> None:
        for p in payloads:
            cid = p.get("chunk_id")
            if cid:
                self.chunk_payloads[str(cid)] = p
        if hasattr(self.graph, "register_payloads"):
            self.graph.register_payloads(self.chunk_payloads)

    def _resolve_hyde_enabled(self, hyde: Any) -> bool:
        if hyde is None:
            if self.hyde_enabled is not None:
                return self.hyde_enabled
            return is_hyde_enabled(self.settings)
        if isinstance(hyde, bool):
            return hyde
        if isinstance(hyde, dict):
            return bool(hyde.get("enabled"))
        return bool(hyde)

    @staticmethod
    def _resolve_hyde_variants(hyde: Any) -> int:
        if isinstance(hyde, dict):
            v = hyde.get("variants")
            if isinstance(v, int) and v > 0:
                return v
        return 1

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 16,
        filters: dict[str, Any] | None = None,
        channel_weights: Mapping[str, float] | None = None,
        include_subgraph: bool = True,
        hyde: dict[str, Any] | bool | None = None,
        recency_window_days: int | None = None,
    ) -> ContextPack:
        filters = dict(filters or {})

        # Pull recency window out of filters (support both documented key names).
        if recency_window_days is None:
            for key in ("recency_window_days", "review_window_days"):
                v = filters.pop(key, None)
                if v is not None:
                    recency_window_days = int(v)
                    break

        # --- pre-hook 1: rule-based query understanding ---
        qu = QueryUnderstanding(raw=query, expanded_query=query)
        if self.enable_query_understanding:
            qu = understand_query(query)

        # --- channel weights: intent bias + explicit override ---
        weights = dict(qu.channel_bias)
        if channel_weights:
            weights.update(channel_weights)

        # --- pre-hook 2: HyDE hypothetical document (vector probe only) ---
        hyde_on = self._resolve_hyde_enabled(hyde)
        hyde_diag: dict[str, Any] = {"enabled": bool(hyde_on)}
        models = list(filters.get("models") or qu.entities or [])
        vector_query: str | None = qu.expanded_query or query
        vector_query_vector: list[float] | None = None
        if hyde_on:
            variants = self._resolve_hyde_variants(hyde)
            t0 = time.perf_counter()
            docs: list[str] = []
            used_llm = False
            for _ in range(max(1, variants)):
                text, used = _generate_hyde(query, models=models, settings=self.settings)
                docs.append(text)
                used_llm = used_llm or used
            if len(docs) == 1:
                vector_query = docs[0]
            else:
                vecs = embed_texts(docs, settings=self.settings)
                avg = [sum(col) / len(vecs) for col in zip(*vecs)]
                vector_query_vector = _normalize(avg)
            hyde_diag.update(
                {
                    "enabled": True,
                    "variants": variants,
                    "used_llm": used_llm,
                    "latency_ms": int((time.perf_counter() - t0) * 1000),
                }
            )

        diagnostics: dict[str, Any] = {
            "channels_failed": [],
            "channel_hits": {},
            "query_understanding": qu.to_dict(),
            "hyde": hyde_diag,
            "recency_window_days": recency_window_days,
        }
        ranked: dict[str, list[str]] = {}
        payload_by_id: dict[str, dict[str, Any]] = dict(self.chunk_payloads)
        if hasattr(self.graph, "register_payloads"):
            self.graph.register_payloads(payload_by_id)

        # Vector
        try:
            v_hits = self.vector.search(
                query=vector_query if vector_query_vector is None else None,
                query_vector=vector_query_vector,
                top_k=max(top_k * 2, 20),
                filters=filters or None,
            )
            ranked["vector"] = [h.chunk_id for h in v_hits]
            diagnostics["channel_hits"]["vector"] = len(v_hits)
            for h in v_hits:
                payload_by_id.setdefault(h.chunk_id, h.payload)
                payload_by_id[h.chunk_id].setdefault("text", h.text)
        except Exception as exc:  # noqa: BLE001
            diagnostics["channels_failed"].append({"channel": "vector", "error": str(exc)})

        # BM25
        try:
            b_hits = self.bm25.search(
                qu.expanded_query or query,
                top_k=max(top_k * 2, 20),
                filters=filters or None,
            )
            ranked["bm25"] = [h.chunk_id for h in b_hits]
            diagnostics["channel_hits"]["bm25"] = len(b_hits)
            for h in b_hits:
                payload_by_id.setdefault(h.chunk_id, h.payload)
                payload_by_id[h.chunk_id].setdefault("text", h.text)
        except Exception as exc:  # noqa: BLE001
            diagnostics["channels_failed"].append({"channel": "bm25", "error": str(exc)})

        # Graph
        try:
            g_hits = self.graph.search_chunks(
                query,
                top_k=max(top_k * 2, 20),
                filters=filters or None,
            )
            ranked["graph"] = [h.chunk_id for h in g_hits]
            diagnostics["channel_hits"]["graph"] = len(g_hits)
            for h in g_hits:
                payload_by_id.setdefault(h.chunk_id, h.payload)
                payload_by_id[h.chunk_id].setdefault("text", h.text)
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
            weights=weights or None,
        )

        now = datetime.now(timezone.utc)
        recency_dropped = 0
        passages: list[Passage] = []
        for chunk_id, score, channels in fused:
            payload = payload_by_id.get(chunk_id, {"chunk_id": chunk_id, "text": ""})
            if filters and not payload_matches_filters(payload, filters):
                continue
            if recency_window_days and not within_recency_window(
                payload, now=now, window_days=recency_window_days
            ):
                recency_dropped += 1
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
            if len(passages) >= top_k:
                break

        diagnostics["rrf_k"] = self.settings.rrf_k
        diagnostics["fused_count"] = len(passages)
        diagnostics["recency_dropped"] = recency_dropped
        return ContextPack(
            query=query,
            passages=passages,
            subgraph=subgraph if include_subgraph else {"nodes": [], "edges": []},
            diagnostics=diagnostics,
        )
