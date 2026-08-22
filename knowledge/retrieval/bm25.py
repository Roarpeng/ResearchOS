"""Simple in-memory BM25 fulltext index (no extra dependencies)."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

from knowledge.retrieval.filters import payload_matches_filters


_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if t.strip()]


@dataclass
class BM25Hit:
    chunk_id: str
    score: float
    text: str
    payload: dict[str, Any] = field(default_factory=dict)


class BM25Index:
    """Okapi BM25 over an in-memory corpus of chunks."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._docs: dict[str, dict[str, Any]] = {}
        self._tf: dict[str, Counter[str]] = {}
        self._df: Counter[str] = Counter()
        self._doc_len: dict[str, int] = {}
        self._avgdl: float = 0.0

    def __len__(self) -> int:
        return len(self._docs)

    def clear(self) -> None:
        self._docs.clear()
        self._tf.clear()
        self._df.clear()
        self._doc_len.clear()
        self._avgdl = 0.0

    def _recompute_avgdl(self) -> None:
        if not self._doc_len:
            self._avgdl = 0.0
            return
        self._avgdl = sum(self._doc_len.values()) / len(self._doc_len)

    def upsert(
        self,
        chunk_id: str,
        text: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if chunk_id in self._tf:
            # remove old df contribution
            for term in self._tf[chunk_id]:
                self._df[term] -= 1
                if self._df[term] <= 0:
                    del self._df[term]
        tokens = tokenize(text)
        tf = Counter(tokens)
        self._tf[chunk_id] = tf
        self._doc_len[chunk_id] = len(tokens)
        self._docs[chunk_id] = {"text": text, "payload": payload or {}}
        for term in tf:
            self._df[term] += 1
        self._recompute_avgdl()

    def upsert_many(self, items: Iterable[tuple[str, str, dict[str, Any] | None]]) -> int:
        n = 0
        for chunk_id, text, payload in items:
            self.upsert(chunk_id, text, payload)
            n += 1
        return n

    def delete(self, chunk_id: str) -> None:
        if chunk_id not in self._tf:
            return
        for term in self._tf[chunk_id]:
            self._df[term] -= 1
            if self._df[term] <= 0:
                del self._df[term]
        del self._tf[chunk_id]
        del self._doc_len[chunk_id]
        del self._docs[chunk_id]
        self._recompute_avgdl()

    def _idf(self, term: str) -> float:
        n = len(self._docs)
        df = self._df.get(term, 0)
        return math.log(1.0 + (n - df + 0.5) / (df + 0.5))

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[BM25Hit]:
        q_terms = tokenize(query)
        if not q_terms or not self._docs:
            return []
        scores: dict[str, float] = defaultdict(float)
        avgdl = self._avgdl or 1.0
        for term in q_terms:
            idf = self._idf(term)
            for chunk_id, tf in self._tf.items():
                f = tf.get(term, 0)
                if f == 0:
                    continue
                dl = self._doc_len.get(chunk_id, 0)
                denom = f + self.k1 * (1 - self.b + self.b * dl / avgdl)
                scores[chunk_id] += idf * (f * (self.k1 + 1)) / denom
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        hits: list[BM25Hit] = []
        for chunk_id, score in ranked:
            doc = self._docs[chunk_id]
            payload = doc["payload"]
            if filters and not payload_matches_filters(payload, filters):
                continue
            hits.append(
                BM25Hit(
                    chunk_id=chunk_id,
                    score=float(score),
                    text=doc["text"],
                    payload=payload,
                )
            )
            if len(hits) >= top_k:
                break
        return hits
