"""Unit tests: report export fallbacks."""

from __future__ import annotations

from pathlib import Path

from tools.report.export import export_report, markdown_to_pdf


def test_markdown_to_pdf_writes_md_without_typst(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("tools.report.export._typst_available", lambda: False)
    md = "# Hello\n\nBody with [^C1]\n"
    out = markdown_to_pdf(md, output_dir=tmp_path, title="T", basename="demo")
    assert out["ok"] is True
    assert out["format"] == "markdown"
    assert (tmp_path / "demo.md").exists()
    assert "typst" in " ".join(out.get("warnings") or []).lower()


def test_export_report_markdown(tmp_path: Path):
    result = export_report(
        "# R\n",
        format="markdown",
        title="R",
        output_dir=tmp_path,
        task_id="tsk_1",
    )
    assert result["ok"] is True
    assert result["format"] == "markdown"
    assert Path(result["path"]).exists()
