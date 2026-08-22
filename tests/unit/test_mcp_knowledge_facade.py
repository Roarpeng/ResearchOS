"""Knowledge facade MCP tests (docs/mcp/05-knowledge-tools.md acceptance)."""

from __future__ import annotations

import pytest

from knowledge.store import get_registry, reset_registry
from tools.knowledge.server import fulltext_search, knowledge_ingest_status, knowledge_retrieve


@pytest.fixture()
def clean_registry():
    reset_registry()
    reg = get_registry()
    reg.reset_memory()
    yield reg
    reset_registry()


def test_knowledge_retrieve_requires_query(clean_registry) -> None:
    res = knowledge_retrieve("   ")
    assert res["ok"] is False
    assert res["error"] == "invalid_argument"


def test_retrieve_after_ingest_returns_provenance(clean_registry) -> None:
    from knowledge.pipeline import KnowledgePipeline

    KnowledgePipeline().ingest_text(
        "# RS-200 spec\nRated torque is 12 Nm with IP67 housing.",
        filename="rs200.md",
        title="RS-200 Datasheet",
    )
    res = knowledge_retrieve("RS-200 rated torque", top_k=4)
    assert res["ok"] is True
    passages = res.get("passages") or []
    assert passages, "expected at least one fused passage"
    first = passages[0]
    # Context Pack passages carry citation provenance fields
    assert first.get("citation")
    assert first.get("source_id")


def test_fulltext_search_hits_ingested_chunk(clean_registry) -> None:
    from knowledge.pipeline import KnowledgePipeline

    KnowledgePipeline().ingest_text(
        "Assembly difficulty: screws need tight tolerance control.",
        filename="pain.md",
        title="Pain points",
    )
    res = fulltext_search("screws tolerance", top_k=3)
    assert isinstance(res["hits"], list)
    assert any("screw" in (h.get("text") or "").lower() for h in res["hits"])


def test_ingest_status_reports_document(clean_registry) -> None:
    from knowledge.pipeline import KnowledgePipeline

    ingest = KnowledgePipeline().ingest_text("hello world doc", filename="hw.md")
    res = knowledge_ingest_status(ingest.doc_id)
    assert res["ok"] is True
    docs = res["documents"]
    assert docs and docs[0]["doc_id"] == ingest.doc_id
    assert docs[0]["status"] in {"ready", "ready_degraded", "parsing", "registered"}

    missing = knowledge_ingest_status("doc_does_not_exist")
    assert missing["ok"] is False and missing["error"] == "not_found"


def test_ingest_status_lists_all(clean_registry) -> None:
    from knowledge.pipeline import KnowledgePipeline

    KnowledgePipeline().ingest_text("alpha", filename="a.md")
    KnowledgePipeline().ingest_text("beta", filename="b.md")
    res = knowledge_ingest_status()
    assert res["count"] >= 2
