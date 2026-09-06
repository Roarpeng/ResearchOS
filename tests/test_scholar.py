"""Scholar unit tests (hermetic: no network)."""

from __future__ import annotations

from tools.scholar import core


def test_extract_dois() -> None:
    text = "see doi:10.1234/abcd and (10.5555/wxyz)."
    assert core.extract_dois(text) == ["10.1234/abcd", "10.5555/wxyz"]


def test_normalize_crossref() -> None:
    item = {
        "DOI": "10.1234/abcd",
        "title": ["A Title"],
        "author": [{"family": "Li", "given": "M."}],
        "container-title": ["J. Plant Sci."],
        "published-print": {"date-parts": [[2020, 1, 1]]},
        "publisher": "ASPJ",
    }
    n = core._normalize_crossref(item)
    assert n["year"] == 2020
    assert n["authors"] == ["M. Li"]
    assert n["journal"] == "J. Plant Sci."
    assert n["url"] == "https://doi.org/10.1234/abcd"


def test_verify_with_injected_resolver() -> None:
    def fake(doi: str) -> dict[str, str] | None:
        return {"doi": doi} if doi == "10.1234/aaaa" else None

    out = core.verify("10.1234/aaaa and 10.9999/bbbb", resolver=fake)
    assert out["total"] == 2
    assert out["resolved"] == 1
    assert out["phantom"] == 1
    assert out["phantom_items"][0]["doi"] == "10.9999/bbbb"
