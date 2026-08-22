"""Unit tests for retrieval v2: query understanding, HyDE, metadata filters,
recency window, and typed graph schema (in-memory backends)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

# Force offline pseudo-embeddings / memory backends.
os.environ.pop("QDRANT_URL", None)
os.environ.pop("NEO4J_URI", None)
os.environ.pop("LITELLM_BASE_URL", None)
os.environ.pop("MINIO_ENDPOINT", None)
os.environ.pop("HYDE_ENABLED", None)

from knowledge.embeddings import pseudo_embed  # noqa: E402
from knowledge.models import Entity, Relation  # noqa: E402
from knowledge.retrieval.bm25 import BM25Index  # noqa: E402
from knowledge.retrieval.graph import (  # noqa: E402
    InMemoryKnowledgeGraph,
    _safe_label,
    _safe_rel_type,
)
from knowledge.retrieval.hybrid import HybridRetriever  # noqa: E402
from knowledge.retrieval.hyde import (  # noqa: E402
    _template_hyde,
    generate_hypothetical_document,
    is_hyde_enabled,
)
from knowledge.retrieval.query_understanding import (  # noqa: E402
    detect_language,
    classify_intent,
    expand_keywords,
    understand_query,
)
from knowledge.retrieval.vector import InMemoryVectorStore  # noqa: E402
from knowledge.settings import KnowledgeSettings, get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _now_delta(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


# --------------------------------------------------------------------------- #
# 1. Query understanding
# --------------------------------------------------------------------------- #
def test_query_understanding_language_and_intent():
    assert detect_language("额定扭矩是多少") == "zh"
    assert detect_language("compare RS-200 vs RS-100") == "en"
    assert detect_language("RS-200 和 RS-100 对比") == "mixed"

    assert classify_intent("RS-200 和 RS-100 哪个扭矩更大？") == "comparison"
    assert classify_intent("有哪些产品支持 EtherCAT？") == "list"
    assert classify_intent("RS-200 额定扭矩是多少") == "question"

    qu = understand_query("RS-200 和 RS-100 哪个扭矩更大？")
    assert qu.intent == "comparison"
    assert qu.entities == ["RS-200", "RS-100"]
    assert qu.channel_bias.get("graph", 1.0) > 1.0


def test_keyword_expansion_keeps_originals():
    expanded, applied = expand_keywords("RS-200 噪音很大")
    assert "噪音" in expanded  # original kept
    assert "noise" in expanded  # synonym appended
    assert "噪音" in applied


def test_need_hyde_only_for_review_queries():
    assert understand_query("RS-200 噪音大吗？").need_hyde is True
    assert understand_query("RS-200 额定扭矩").need_hyde is False


# --------------------------------------------------------------------------- #
# 2. HyDE
# --------------------------------------------------------------------------- #
def test_hyde_template_deterministic_and_anchored():
    a = _template_hyde("噪音大吗", ["RS-200"])
    b = _template_hyde("噪音大吗", ["RS-200"])
    assert a == b
    assert "噪音大吗" in a
    assert "RS-200" in a


def test_hyde_public_api_returns_template_without_llm():
    doc = generate_hypothetical_document("噪音大吗", models=["RS-200"], use_llm=False)
    assert "噪音大吗" in doc


def test_hyde_llm_failure_falls_back_to_template(monkeypatch):
    import knowledge.retrieval.hyde as hyde_mod

    monkeypatch.setattr(hyde_mod, "_llm_hyde", lambda *a, **k: None)
    doc = generate_hypothetical_document("噪音大吗", use_llm=True)
    assert "噪音大吗" in doc


def test_hyde_enabled_default_off():
    settings = KnowledgeSettings()
    assert is_hyde_enabled(settings) is False


# --------------------------------------------------------------------------- #
# 3. Metadata filters across channels
# --------------------------------------------------------------------------- #
def _chunk_payload(chunk_id: str, text: str, **extra):
    p = {
        "chunk_id": chunk_id,
        "text": text,
        "source_id": chunk_id,
        "doc_id": f"doc-{chunk_id}",
        "section_type": "review",
    }
    p.update(extra)
    return p


def test_vector_filter_source_id_tags_doc_type_created():
    store = InMemoryVectorStore()
    store.upsert("a", pseudo_embed("noise torque"), _chunk_payload(
        "a", "noise torque", source_id="src-a", tags=["motor", "noise"],
        doc_type="review", timestamp=_now_delta(10)))
    store.upsert("b", pseudo_embed("noise torque"), _chunk_payload(
        "b", "noise torque", source_id="src-b", tags=["gripper"],
        doc_type="specification", timestamp=_now_delta(200)))

    assert [h.chunk_id for h in store.search("noise", top_k=10, filters={"source_id": "src-a"})] == ["a"]
    assert [h.chunk_id for h in store.search("noise", top_k=10, filters={"tags": ["motor"]})] == ["a"]
    assert [h.chunk_id for h in store.search("noise", top_k=10, filters={"doc_type": "specification"})] == ["b"]
    assert [h.chunk_id for h in store.search("noise", top_k=10, filters={"created_after": _now_delta(30)})] == ["a"]
    assert [h.chunk_id for h in store.search("noise", top_k=10, filters={"created_before": _now_delta(30)})] == ["b"]


def test_bm25_filter_source_id_and_doc_type():
    idx = BM25Index()
    idx.upsert("a", "noise torque", _chunk_payload("a", "noise torque", source_id="src-a", doc_type="review"))
    idx.upsert("b", "noise torque", _chunk_payload("b", "noise torque", source_id="src-b", doc_type="specification"))
    assert [h.chunk_id for h in idx.search("noise", top_k=10, filters={"source_id": "src-b"})] == ["b"]
    assert [h.chunk_id for h in idx.search("noise", top_k=10, filters={"doc_type": "review"})] == ["a"]


def test_graph_filter_source_id_and_tags():
    graph = InMemoryKnowledgeGraph()
    graph.register_payloads({
        "a": _chunk_payload("a", "noise torque", source_id="src-a", tags=["motor"]),
        "b": _chunk_payload("b", "noise torque", source_id="src-b", tags=["gripper"]),
    })
    prod = Entity(type="Product", canonical_key="product:rs-200", name="RS-200")
    graph.upsert_entities([prod])
    graph.upsert_relations([
        Relation(type="REFERENCES", from_key="product:rs-200", to_key="a",
                 from_type="Product", to_type="Chunk", properties={"chunk_id": "a"}),
        Relation(type="REFERENCES", from_key="product:rs-200", to_key="b",
                 from_type="Product", to_type="Chunk", properties={"chunk_id": "b"}),
    ])
    hits = graph.search_chunks("RS-200", top_k=10, filters={"source_id": "src-a"})
    assert [h.chunk_id for h in hits] == ["a"]


def test_hybrid_retrieve_metadata_filter_end_to_end():
    vec = InMemoryVectorStore()
    bm25 = BM25Index()
    graph = InMemoryKnowledgeGraph()
    payloads = {
        "a": _chunk_payload("a", "RS-200 noise torque", source_id="src-a", doc_type="review"),
        "b": _chunk_payload("b", "RS-200 noise torque", source_id="src-b", doc_type="specification"),
    }
    for cid, p in payloads.items():
        vec.upsert(cid, pseudo_embed(p["text"]), p)
        bm25.upsert(cid, p["text"], p)
    hybrid = HybridRetriever(vec, bm25, graph, chunk_payloads=payloads)
    pack = hybrid.retrieve("RS-200 noise", top_k=10, filters={"source_id": "src-a"})
    assert pack.passages
    assert all(p.citation.source_id == "src-a" for p in pack.passages)


# --------------------------------------------------------------------------- #
# 4. Recency window
# --------------------------------------------------------------------------- #
def test_recency_window_drops_old_timestamped_chunks():
    vec = InMemoryVectorStore()
    bm25 = BM25Index()
    graph = InMemoryKnowledgeGraph()
    payloads = {
        "recent": _chunk_payload("recent", "noise review", timestamp=_now_delta(10)),
        "old": _chunk_payload("old", "noise review", timestamp=_now_delta(60)),
        "untyped": _chunk_payload("untyped", "noise review"),  # no timestamp
    }
    for cid, p in payloads.items():
        vec.upsert(cid, pseudo_embed(p["text"]), p)
        bm25.upsert(cid, p["text"], p)
    hybrid = HybridRetriever(vec, bm25, graph, chunk_payloads=payloads)
    pack = hybrid.retrieve("noise review", top_k=10, recency_window_days=30)
    ids = {p.chunk_id for p in pack.passages}
    assert "old" not in ids
    assert "recent" in ids
    assert "untyped" in ids
    assert pack.diagnostics["recency_dropped"] >= 1


# --------------------------------------------------------------------------- #
# 5. Typed graph schema (in-memory parity)
# --------------------------------------------------------------------------- #
def test_graph_merge_on_type_and_name():
    graph = InMemoryKnowledgeGraph()
    a = Entity(type="Product", canonical_key="product:rs-200", name="RS-200", properties={"models": ["RS-200"]})
    b = Entity(type="Product", canonical_key="product:rs-200", name="RS-200", properties={"category": "servo"})
    graph.upsert_entities([a, b])
    assert len(graph.entities) == 1
    merged = graph.entities["product:rs-200"]
    assert merged.properties["models"] == ["RS-200"]
    assert merged.properties["category"] == "servo"


def test_references_materialize_chunk_node():
    graph = InMemoryKnowledgeGraph()
    prod = Entity(type="Product", canonical_key="product:rs-200", name="RS-200")
    graph.upsert_entities([prod])
    graph.upsert_relations([
        Relation(type="REFERENCES", from_key="product:rs-200", to_key="chk_9",
                 from_type="Product", to_type="Chunk", properties={"chunk_id": "chk_9"}),
    ])
    assert "chk_9" in graph.chunks
    result = graph.query("", top_k=10)
    assert "chk_9" in [c["chunk_id"] for c in result.get("chunks", [])]


def test_extraction_emits_updated_by_edge():
    from knowledge.extract.entities import extract_from_text

    entities, relations = extract_from_text(
        "RS-200 额定扭矩 12 Nm", chunk_id="chk_1", doc_id="doc_1"
    )
    types = {e.type for e in entities}
    assert "Document" in types
    updated = [r for r in relations if r.type == "UPDATED_BY"]
    assert updated
    assert updated[0].from_key == "product:rs-200"
    assert updated[0].to_key == "document:doc_1"
    assert updated[0].to_type == "Document"


def test_typed_label_helpers():
    assert _safe_label("Product") == "Product"
    assert _safe_label(None, "product:rs-200") == "Product"
    assert _safe_label("PainPoint") == "PainPoint"
    assert _safe_label("NotARealType", "weird:thing") == "Entity"
    assert _safe_rel_type("UPDATED_BY") == "UPDATED_BY"
    assert _safe_rel_type("HAS_FEATURE") == "HAS_FEATURE"
    assert _safe_rel_type("weird") == "RELATED"


# --------------------------------------------------------------------------- #
# 6. Backward compatibility
# --------------------------------------------------------------------------- #
def test_hybrid_retrieve_basic_roundtrip_still_works():
    vec = InMemoryVectorStore()
    bm25 = BM25Index()
    graph = InMemoryKnowledgeGraph()
    payloads = {"a": _chunk_payload("a", "RS-200 rated torque 12 Nm")}
    for cid, p in payloads.items():
        vec.upsert(cid, pseudo_embed(p["text"]), p)
        bm25.upsert(cid, p["text"], p)
    hybrid = HybridRetriever(vec, bm25, graph, chunk_payloads=payloads)
    pack = hybrid.retrieve("RS-200 torque", top_k=5)
    assert pack.query == "RS-200 torque"
    assert pack.passages
    assert pack.diagnostics["hyde"]["enabled"] is False
    assert "query_understanding" in pack.diagnostics
