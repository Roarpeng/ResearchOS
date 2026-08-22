"""Parser router v2 tests — Docling / Unstructured / MarkItDown lazy fallback chain.

Runs without any optional dependencies installed: md/txt pass through the text
engine, html resolves the full fallback chain down to text, and PARSER_ENGINE
forces the text engine. The markitdown path is asserted only when that optional
package happens to be importable.
"""

from __future__ import annotations

import pytest

from knowledge.models import ParseIR
from knowledge.parsers.router import parse_document


def _md_doc() -> bytes:
    return "# 产品规格\n\n额定扭矩 12 Nm。\n".encode("utf-8")


def _html_doc() -> bytes:
    return (
        "<html><head><title>t</title></head><body>"
        "<h1>产品规格</h1><p>额定扭矩 12 Nm</p>"
        "<script>alert(1)</script><nav>导航噪声</nav>"
        "<p>更多正文。</p></body></html>"
    ).encode("utf-8")


def test_md_text_pass_through():
    ir = parse_document(_md_doc(), doc_id="doc_md", filename="a.md")
    assert isinstance(ir, ParseIR)
    assert ir.parser["name"] == "text"
    assert ir.parser["engine_selected"] == "text"
    assert ir.parser["fallback_chain"] == "text"
    assert ir.pages
    assert any(b.text for p in ir.pages for b in p.blocks)


def test_html_fallback_chain_produces_blocks():
    ir = parse_document(_html_doc(), doc_id="doc_html", filename="page.html")
    assert isinstance(ir, ParseIR)
    blocks = [b for p in ir.pages for b in p.blocks]
    assert blocks, "html fallback chain must produce non-empty blocks"
    assert any(b.text for b in blocks)
    # fallback chain recorded in parser metadata
    chain = ir.parser["fallback_chain"].split(",")
    assert "text" in chain
    assert "unstructured" in chain
    assert chain[-1] == "text"
    # degradation reasons recorded in warnings
    assert any("unavailable" in w for w in ir.warnings)


def test_parser_engine_text_forced(monkeypatch):
    monkeypatch.setenv("PARSER_ENGINE", "text")
    ir = parse_document(_html_doc(), doc_id="doc_forced", filename="page.html")
    assert ir.parser["engine_selected"] == "text"
    assert ir.parser["name"] == "text"
    assert ir.parser["fallback_chain"] == "text"
    assert any(b.text for p in ir.pages for b in p.blocks)


def test_parser_metadata_records_fallback_chain():
    ir = parse_document(_html_doc(), doc_id="doc_meta", filename="page.html")
    meta = ir.parser
    assert meta.get("name")
    assert meta.get("engine_selected")
    chain = meta.get("fallback_chain", "")
    assert chain
    assert chain.split(",")[-1] == "text"


def test_markitdown_available_path_optional(tmp_path):
    pytest.importorskip("markitdown")
    from knowledge.parsers.router import MarkItDownProvider, parse_markitdown

    provider = MarkItDownProvider()
    assert provider.available is True

    md = tmp_path / "sample.md"
    md.write_text("# 标题\n\n正文。", encoding="utf-8")
    ir = parse_markitdown(md.read_bytes(), "doc_md", str(md))
    assert ir.parser["name"] == "markitdown"
    assert ir.markdown.strip()
    assert ir.pages
