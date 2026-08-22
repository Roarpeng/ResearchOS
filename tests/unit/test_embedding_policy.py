"""Embedding policy tests (docs/knowledge/08-embedding-strategy.md)."""

from __future__ import annotations

import pytest

from knowledge.embeddings import (
    EMBEDDING_MODELS,
    EmbeddingPolicy,
    active_embed_model,
    assert_model_compatible,
    collection_name,
    embed_with_meta,
    resolve_embedding_policy,
)
from knowledge.settings import KnowledgeSettings


def _settings(**overrides: object) -> KnowledgeSettings:
    return KnowledgeSettings(
        embedding_dim=64,
        **overrides,  # type: ignore[arg-type]
    )


def test_default_resolves_to_pseudo_without_keys() -> None:
    """Clean env without cloud keys falls through to the offline default."""
    policy = resolve_embedding_policy(_settings())
    assert policy.provider == "pseudo_v1"
    assert policy.dim == 64
    assert policy.is_local is True


def test_require_local_skips_cloud_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    cfg = _settings(embedding_priority="openai,bge_m3,pseudo_v1", embedding_require_local=True)
    policy = resolve_embedding_policy(cfg)
    assert policy.provider == "pseudo_v1"  # bge_m3 runtime not installed in CI


def test_cloud_key_promotes_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    cfg = _settings(embedding_priority="openai,bge_m3,pseudo_v1")
    policy = resolve_embedding_policy(cfg)
    assert policy.provider == "openai"
    assert policy.dim == EMBEDDING_MODELS["openai"]["dim"]


def test_unknown_providers_are_skipped() -> None:
    cfg = _settings(embedding_priority="does_not_exist,pseudo_v1")
    assert resolve_embedding_policy(cfg).provider == "pseudo_v1"


def test_embed_with_meta_stamps_model() -> None:
    vectors, policy = embed_with_meta(["hello world", "second text"], settings=_settings())
    assert len(vectors) == 2
    assert policy.provider == "pseudo_v1"


def test_collection_naming_convention() -> None:
    name = collection_name("ws-demo", "bge_m3", 1024)
    assert name == "chunks_ws_demo_bge_m3_1024"


def test_model_compatibility_guard() -> None:
    assert assert_model_compatible(None, "pseudo_v1") is True  # legacy points stay
    assert assert_model_compatible("", "pseudo_v1") is True
    assert assert_model_compatible("pseudo_v1", "pseudo_v1") is True
    assert assert_model_compatible("openai", "pseudo_v1") is False


def test_vector_search_rejects_mismatched_models() -> None:
    from knowledge.retrieval.vector import InMemoryVectorStore

    store = InMemoryVectorStore()
    store.upsert("chk_legacy", [1.0, 0.0], {"chunk_id": "chk_legacy", "text": "legacy"})
    store.upsert(
        "chk_foreign",
        [1.0, 0.0],
        {"chunk_id": "chk_foreign", "text": "foreign model", "embed_model": "openai"},
    )
    hits = store.search("legacy")
    ids = {h.chunk_id for h in hits}
    assert "chk_legacy" in ids
    assert "chk_foreign" not in ids


def test_active_model_matches_policy() -> None:
    cfg = _settings(embedding_priority="voyage,pseudo_v1")  # no key → pseudo
    assert active_embed_model(cfg) == "pseudo_v1"


def test_delete_by_doc_memory_backend() -> None:
    from knowledge.retrieval.vector import InMemoryVectorStore

    store = InMemoryVectorStore()
    for i in range(3):
        store.upsert(f"c{i}", [float(i), 1.0], {"chunk_id": f"c{i}", "doc_id": "doc_1"})
    store.upsert("other", [9.0, 1.0], {"chunk_id": "other", "doc_id": "doc_2"})
    removed = store.delete_by_doc("doc_1")
    assert removed == 3
    assert len(store) == 1
