"""Embedding helpers: LiteLLM when available, else deterministic hash vectors."""

from __future__ import annotations

import hashlib
import logging
import math
import struct
from typing import Sequence

import httpx

from knowledge.settings import KnowledgeSettings, get_settings

logger = logging.getLogger("researchos.knowledge.embeddings")


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def pseudo_embed(text: str, dim: int = 64) -> list[float]:
    """Deterministic pseudo-embedding for offline tests (no model required)."""
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    counter = 0
    while len(values) < dim:
        block = hashlib.sha256(seed + counter.to_bytes(4, "little")).digest()
        for i in range(0, len(block) - 3, 4):
            (u,) = struct.unpack_from("<I", block, i)
            values.append((u / 0xFFFFFFFF) * 2.0 - 1.0)
            if len(values) >= dim:
                break
        counter += 1
    # Mix token presence lightly so shared tokens increase similarity.
    tokens = {t.lower() for t in text.split() if t.strip()}
    for i, tok in enumerate(sorted(tokens)):
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest()[:8], 16)
        values[h % dim] += 0.15
        values[(h // dim) % dim] += 0.05 * ((i % 3) - 1)
    return _l2_normalize(values[:dim])


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return float(sum(x * y for x, y in zip(a, b)))


def _litellm_embed(texts: list[str], settings: KnowledgeSettings) -> list[list[float]] | None:
    if not settings.litellm_base_url:
        return None
    url = settings.litellm_base_url.rstrip("/") + "/v1/embeddings"
    headers = {"Content-Type": "application/json"}
    if settings.litellm_master_key:
        headers["Authorization"] = f"Bearer {settings.litellm_master_key}"
    payload = {"model": settings.embedding_model, "input": texts}
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            if resp.status_code >= 400:
                logger.warning("LiteLLM embeddings HTTP %s: %s", resp.status_code, resp.text[:200])
                return None
            data = resp.json()
            items = data.get("data") or []
            items = sorted(items, key=lambda x: x.get("index", 0))
            vectors = [list(map(float, item["embedding"])) for item in items]
            if len(vectors) != len(texts):
                logger.warning("LiteLLM embedding count mismatch")
                return None
            return [_l2_normalize(v) for v in vectors]
    except Exception as exc:  # noqa: BLE001 — degrade to pseudo-embed
        logger.warning("LiteLLM embeddings unavailable: %s", exc)
        return None


def embed_texts(
    texts: Sequence[str],
    *,
    settings: KnowledgeSettings | None = None,
    force_pseudo: bool = False,
) -> list[list[float]]:
    """Embed texts via LiteLLM if configured; otherwise hash pseudo-embeddings."""
    cfg = settings or get_settings()
    clean = [t if t is not None else "" for t in texts]
    if not clean:
        return []
    if not force_pseudo:
        vectors = _litellm_embed(clean, cfg)
        if vectors is not None:
            return vectors
    return [pseudo_embed(t, dim=cfg.embedding_dim) for t in clean]


def embed_query(query: str, *, settings: KnowledgeSettings | None = None) -> list[float]:
    return embed_texts([query], settings=settings)[0]
