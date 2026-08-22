"""Embedding helpers: LiteLLM when available, else deterministic hash vectors."""

from __future__ import annotations

import hashlib
import logging
import math
import struct
from dataclasses import dataclass
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


# ---------------------------------------------------------------------------
# Embedding policy (docs/knowledge/08-embedding-strategy.md)
# ---------------------------------------------------------------------------

EMBEDDING_MODELS: dict[str, dict[str, object]] = {
    "voyage": {"model": "voyage/voyage-3-large", "dim": 1024, "local": False},
    "openai": {"model": "text-embedding-3-large", "dim": 3072, "local": False},
    "bge_m3": {"model": "BAAI/bge-m3", "dim": 1024, "local": True},
    "nomic": {"model": "nomic-embed-text", "dim": 768, "local": True},
    # Deterministic offline fallback — always available, tests/air-gap default.
    "pseudo_v1": {"model": "pseudo-hash-v1", "dim": 64, "local": True},
}

_CLOUD_KEY_ENV = {
    "voyage": ("VOYAGE_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
}


def _provider_available(provider: str) -> bool:
    if provider == "pseudo_v1":
        return True
    info = EMBEDDING_MODELS.get(provider) or {}
    env_names = _CLOUD_KEY_ENV.get(provider)
    if env_names:
        import os

        return any(os.getenv(name or "", "").strip() for name in env_names if name)
    if provider == "bge_m3":
        try:
            import FlagEmbedding  # noqa: F401
        except ImportError:
            return False
        return True
    if provider == "nomic":
        try:
            import sentence_transformers  # noqa: F401
        except ImportError:
            return False
        return True
    return False


@dataclass
class EmbeddingPolicy:
    """Resolved embedding route: one model id + dim per active collection."""

    provider: str
    dim: int

    @property
    def slug(self) -> str:
        return self.provider

    @property
    def is_local(self) -> bool:
        return bool((EMBEDDING_MODELS.get(self.provider) or {}).get("local"))


def resolve_embedding_policy(
    settings: KnowledgeSettings | None = None,
) -> EmbeddingPolicy:
    """Pick the highest-priority available provider (docs/08 配置模型)."""
    cfg = settings or get_settings()
    priority = [p.strip() for p in cfg.embedding_priority.split(",") if p.strip()]
    require_local = cfg.embedding_require_local or cfg.embedding_policy == "local_only"
    for provider in priority:
        info = EMBEDDING_MODELS.get(provider)
        if info is None:
            continue
        if require_local and not info.get("local"):
            continue
        if not _provider_available(provider):
            continue
        dim = int(info["dim"]) if info.get("dim") else cfg.embedding_dim
        if provider == "pseudo_v1":
            dim = cfg.embedding_dim
        return EmbeddingPolicy(provider=provider, dim=dim)
    return EmbeddingPolicy(provider="pseudo_v1", dim=cfg.embedding_dim)


def collection_name(workspace_id: str, slug: str, dim: int) -> str:
    """Per docs/08 命名建议: chunks_{workspace}_{model_slug}_{dim}."""
    safe_ws = "".join(ch if ch.isalnum() else "_" for ch in (workspace_id or "default"))
    return f"chunks_{safe_ws}_{slug}_{dim}"


def active_embed_model(settings: KnowledgeSettings | None = None) -> str:
    """Model id of the currently resolved embedding route."""
    return resolve_embedding_policy(settings).provider


def embed_with_meta(
    texts: Sequence[str],
    *,
    settings: KnowledgeSettings | None = None,
) -> tuple[list[list[float]], EmbeddingPolicy]:
    """Embed via the resolved policy; deterministic fallback guarantees success."""
    cfg = settings or get_settings()
    clean = [t if t is not None else "" for t in texts]
    if not clean:
        return [], resolve_embedding_policy(cfg)
    policy = resolve_embedding_policy(cfg)
    if policy.provider == "pseudo_v1":
        return [pseudo_embed(t, dim=policy.dim) for t in clean], policy
    vectors = _litellm_embed(clean, cfg)
    if vectors is None and policy.provider in {"bge_m3", "nomic"}:
        # Local model runtimes are optional heavy deps; degrade deterministically.
        logger.warning("local embedding provider %s unavailable; using pseudo_v1", policy.provider)
        policy = EmbeddingPolicy(provider="pseudo_v1", dim=cfg.embedding_dim)
        return [pseudo_embed(t, dim=policy.dim) for t in clean], policy
    if vectors is not None:
        return vectors, policy
    return [pseudo_embed(t, dim=policy.dim) for t in clean], EmbeddingPolicy(
        provider="pseudo_v1", dim=cfg.embedding_dim
    )


def assert_model_compatible(payload_model: object, active_model: str) -> bool:
    """True when a stored point may be queried with the active model.

    Points without an ``embed_model`` stamp (legacy) stay queryable; explicit
    mismatches are rejected per docs/08 「禁止用模型 A 查 collection B」.
    """
    if payload_model in (None, "", active_model):
        return True
    return False
