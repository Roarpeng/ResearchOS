"""Report MCP validation/preview tests (docs/mcp/06 acceptance #3)."""

from __future__ import annotations

from tools.report.export import report_preview, validate_citations

_CITATIONS = [
    {"id": "C1", "title": "ISO TS 15066", "url": "https://iso.org/ts15066"},
    {"id": "C2", "title": "Vendor datasheet", "source_id": "doc_123", "locator": "p.4"},
]


def test_all_markers_resolve_passes() -> None:
    md = (
        "# Report\n\n协作机器人符合 [^C1] 规范；额定扭矩 12 Nm 见 [^C2]。\n\n"
        "[^C1]: ISO TS 15066, https://iso.org/ts15066\n"
        "[^C2]: Vendor datasheet, p.4\n"
    )
    res = validate_citations(md, _CITATIONS)
    assert res["ok"] is True
    assert res["citation_stats"]["markers"] == 2
    assert res["citation_stats"]["unresolved_markers"] == 0


def test_unresolved_marker_fails_strict_warn_ok() -> None:
    md = "断言一 [^C1]；断言二 [^C9]。"
    strict = validate_citations(md, _CITATIONS, on_policy="strict")
    assert strict["ok"] is False
    assert strict["error"] == "citation_incomplete"
    assert "C9" in strict["unresolved"]

    warn = validate_citations(md, _CITATIONS, on_policy="warn")
    assert warn["ok"] is False
    assert "error" not in warn


def test_citation_missing_provenance_flagged() -> None:
    bad = [{"id": "C1", "title": "no provenance"}]
    res = validate_citations("claim [^C1]", bad)
    assert res["ok"] is False
    assert res["invalid"][0]["reason"] == "missing_provenance"


def test_bracket_style_marker_supported() -> None:
    md = "结论 [citation:C1]。"
    res = validate_citations(md, _CITATIONS)
    assert res["ok"] is True
    assert res["citation_stats"]["markers"] == 1


def test_report_preview_summarizes_without_side_effects() -> None:
    md = "# T\n\n## 摘要\n内容 [^C1]\n\n## 风险\nx"
    res = report_preview(md, title="Demo", citations=_CITATIONS)
    assert res["ok"] is True
    assert res["sections"] == 2
    assert "摘要" in res["head"]
    assert res["citation_check_ok"] is True
