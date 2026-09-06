"""Draft assembler unit tests."""

from __future__ import annotations

from scientific.manuscript.draft import assemble_sections


def test_assemble_sections_with_provenance() -> None:
    outline = {"sections": [{"key": "results", "title": "Results"}]}
    chunks = [
        {"section": "results", "source_id": "doc_1", "chunk_id": "chk_1", "locator": "p3", "text": "wheat yield +12%"},
        {"section": "results", "source_id": "doc_2", "chunk_id": "chk_2", "locator": "p5", "text": "rice drought improved"},
    ]
    sections = assemble_sections(outline, chunks)
    assert len(sections) == 1
    s = sections[0]
    assert s.key == "results" and s.title == "Results"
    assert "wheat yield +12%" in s.body
    assert len(s.records) == 2
    assert s.records[0].sources[0].source_id == "doc_1"
    assert s.records[0].sources[0].locator == "p3"


def test_default_sections_when_outline_empty() -> None:
    sections = assemble_sections({}, [{"source_id": "d", "chunk_id": "c", "text": "x"}])
    assert [s.key for s in sections] == [
        "introduction",
        "materials",
        "results",
        "discussion",
        "conclusion",
    ]
