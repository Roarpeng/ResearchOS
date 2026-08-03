"""Unit tests for semantic chunking."""

from __future__ import annotations

from knowledge.chunking.semantic import chunk_parse_ir, chunk_text, section_type_histogram
from knowledge.parsers.router import parse_document


SAMPLE_MD = """# RS-200 产品手册

## 规格

RS-200 是一款工业关节模组。

## 参数

额定扭矩: 12 Nm
峰值扭矩: 36 Nm

## FAQ

Q: 如何安装？
A: 使用 M4 螺丝固定法兰。

## 用户评价

装配有点困难，螺丝公差偏紧。
"""


def test_chunk_text_structure_types():
    chunks = chunk_text(SAMPLE_MD, doc_id="doc_test", source_file="rs200.md")
    assert chunks
    hist = section_type_histogram(chunks)
    assert hist.get("title", 0) >= 1
    assert hist.get("parameter", 0) + hist.get("specification", 0) >= 1
    assert any(c.source_id == "doc_test" for c in chunks)
    assert all(c.locator is not None for c in chunks)
    # FAQ should keep Q+A together when possible
    faq_chunks = [c for c in chunks if c.section_type == "faq"]
    assert faq_chunks
    assert any("安装" in c.text for c in faq_chunks)


def test_parent_child_metadata_on_long_section():
    from knowledge.settings import KnowledgeSettings

    long_body = "句子。" * 800
    text = f"# 标题\n\n## 参数\n\n{long_body}"
    settings = KnowledgeSettings(CHUNK_SOFT_MAX_CHARS=200, CHUNK_HARD_MAX_CHARS=400)
    chunks = chunk_text(text, doc_id="doc_long", settings=settings)
    assert len(chunks) >= 2
    children = [c for c in chunks if c.parent_chunk_id or c.parent_section_id]
    assert children


def test_parse_then_chunk_roundtrip_fields():
    data = SAMPLE_MD.encode("utf-8")
    ir = parse_document(data, doc_id="doc_rt", filename="manual.md")
    chunks = chunk_parse_ir(ir)
    assert chunks
    for c in chunks:
        assert c.doc_id == "doc_rt"
        assert c.source_id == "doc_rt"
        assert c.content_hash
        assert c.text.strip()
