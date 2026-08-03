"""In-memory ingest → hybrid search roundtrip."""

from __future__ import annotations

import os

import pytest

# Force offline pseudo-embeddings / memory backends
os.environ.pop("QDRANT_URL", None)
os.environ.pop("NEO4J_URI", None)
os.environ.pop("LITELLM_BASE_URL", None)
os.environ.pop("MINIO_ENDPOINT", None)


@pytest.fixture()
def pipeline(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_OBJECTS_DIR", str(tmp_path / "objects"))
    from knowledge.settings import get_settings
    from knowledge.store import reset_registry

    get_settings.cache_clear()
    reg = reset_registry()
    from knowledge.pipeline import KnowledgePipeline

    return KnowledgePipeline(reg)


DOC = """# Acme RS-200 Manual

## 参数

额定扭矩: 12 Nm
峰值扭矩: 36 Nm

RS-200 与 RS-100 对比时，RS-200 扭矩更高。

## 用户评价

装配困难，螺丝公差问题明显。
"""


def test_ingest_search_roundtrip(pipeline):
    result = pipeline.ingest_text(DOC, filename="rs200.md", title="RS-200")
    assert result.status in {"ready", "ready_degraded"}
    assert result.chunk_count > 0
    assert result.channels.get("vector") is True
    assert result.channels.get("bm25") is True

    pack = pipeline.search("RS-200 额定扭矩", top_k=5)
    assert pack["query"]
    assert pack["passages"], "expected hybrid passages"
    top = pack["passages"][0]
    assert top["citation"]["source_id"]
    assert top["citation"]["locator"] is not None
    assert "扭矩" in top["text"] or "RS-200" in top["text"]
    assert top["channels"]


def test_bm25_exact_model_hit(pipeline):
    pipeline.ingest_text(DOC, filename="rs200.md")
    pack = pipeline.search("RS-200", top_k=3)
    texts = " ".join(p["text"] for p in pack["passages"])
    assert "RS-200" in texts


def test_graph_entities_extracted(pipeline):
    result = pipeline.ingest_text(DOC, filename="rs200.md")
    assert result.entity_count >= 1
    graph = pipeline.registry.graph.query("RS-200", top_k=10)
    assert graph["nodes"] or graph["evidence_chunk_ids"]
