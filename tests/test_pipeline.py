"""Manuscript pipeline end-to-end test (local fallbacks, no LLM)."""

from __future__ import annotations

from scientific.manuscript.pipeline import run_pipeline


def test_run_pipeline_produces_journalized_html(tmp_path) -> None:
    (tmp_path / "wheat.md").write_text(
        "# Wheat\nNitrogen fertilizer increased wheat grain yield significantly.\n",
        encoding="utf-8",
    )
    (tmp_path / "rice.txt").write_text(
        "Rice drought tolerance improved by OsNAC transcription factor.\n",
        encoding="utf-8",
    )

    result = run_pipeline(tmp_path, "nitrogen fertilizer wheat", ["A. Li"], "Abstract here.")

    assert result["passed"] is True
    assert result["chunks"] > 0
    assert result["sections"] == ["Introduction", "Results", "Discussion"]
    assert "nitrogen fertilizer wheat" in result["html"]
    assert "AI Use Disclosure" in result["html"]
    assert result["manifest"]["title"] == "nitrogen fertilizer wheat"
