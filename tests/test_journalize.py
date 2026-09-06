"""Journalize unit tests (uses committed crop-journal style)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scientific.manuscript.draft import DraftSection, assemble_sections
from scientific.manuscript.journalize import build_manifest, load_journal_style, render_html

_STYLE = Path(__file__).resolve().parents[1] / "scientific" / "journal_styles" / "crop-journal.json"


def test_load_style() -> None:
    style = load_journal_style(_STYLE)
    assert style["journal"] == "Crop Journal"
    assert style["typography"]["fontFamily"] == "Times New Roman"


def test_render_html_includes_style_and_disclosure() -> None:
    style = load_journal_style(_STYLE)
    sections = assemble_sections({"sections": [{"key": "results", "title": "Results"}]}, [
        {"section": "results", "source_id": "doc_1", "chunk_id": "chk_1", "text": "wheat yield +12%"},
    ])
    html_out = render_html(
        title="A Crop Study",
        authors=["A. Li", "B. Wang"],
        abstract="Abstract text.",
        sections=sections,
        style=style,
        ai_disclosure="AI used with human verification.",
        references=["Li et al. 2024"],
    )
    assert "A Crop Study" in html_out
    assert "Times New Roman" in html_out
    assert "AI Use Disclosure" in html_out
    assert "Li et al. 2024" in html_out
    assert "wheat yield +12%" in html_out


def test_build_manifest() -> None:
    m = build_manifest(
        journal="Crop Journal",
        title="T",
        authors=["A"],
        figure_count=3,
        ai_disclosure="d",
    )
    assert m["figure_count"] == 3
    assert m["journal"] == "Crop Journal"


def test_render_markdown_intermediate() -> None:
    from scientific.manuscript.journalize import render_markdown

    sections = assemble_sections({"sections": [{"key": "results", "title": "Results"}]}, [
        {"section": "results", "source_id": "doc_1", "chunk_id": "chk_1", "text": "wheat yield +12%"},
    ])
    md = render_markdown(
        title="T",
        authors=["A"],
        abstract="Abs.",
        sections=sections,
        ai_disclosure="d",
        references=["Li et al. 2024"],
    )
    assert md.startswith("# T")
    assert "## Abstract" in md
    assert "## Results" in md
    assert md.count("## Results") == 1  # assembler heading deduped
    assert "## AI Use Disclosure" in md
    assert "- Li et al. 2024" in md


def test_render_docx(tmp_path) -> None:
    pytest.importorskip("pypandoc")
    from scientific.manuscript.journalize import render_docx, render_markdown

    sections = assemble_sections({"sections": [{"key": "results", "title": "Results"}]}, [
        {"section": "results", "source_id": "doc_1", "chunk_id": "chk_1", "text": "wheat yield +12%"},
    ])
    md = render_markdown(
        title="T", authors=["A"], abstract="Abs.", sections=sections,
        ai_disclosure="d", references=["Li et al. 2024"],
    )
    out = render_docx(md, tmp_path / "manuscript.docx")
    assert out["ok"] is True
    assert (tmp_path / "manuscript.docx").stat().st_size > 0
