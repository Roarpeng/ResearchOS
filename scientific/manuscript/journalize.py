"""Journalize: render draft sections into a journal-styled standalone HTML + manifest.

Uses scientific/journal_styles/*.json; PDF/DOCX rendering is delegated to
tools/report (Typst/Pandoc) or the frontend export engine (ADR-0011).
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from scientific.manuscript.draft import DraftSection


def load_journal_style(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _body_to_html(body: str) -> str:
    parts: list[str] = []
    for line in body.splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        if line.startswith("## "):
            continue  # section title rendered separately
        if line.startswith("> "):
            parts.append(f"<blockquote>{html.escape(line[2:])}</blockquote>")
        else:
            parts.append(f"<p>{html.escape(line)}</p>")
    return "\n".join(parts)


def render_html(
    *,
    title: str,
    authors: list[str],
    abstract: str,
    sections: list[DraftSection],
    style: dict[str, Any],
    ai_disclosure: str,
    references: list[str],
) -> str:
    typography = style.get("typography") or {}
    font = typography.get("fontFamily", "Times New Roman")
    size = typography.get("fontSizePt", 11)
    line = typography.get("lineSpacing", 1.5)

    authors_html = ", ".join(html.escape(a) for a in authors)
    sections_html = "\n".join(
        f"<section><h2>{html.escape(s.title)}</h2>{_body_to_html(s.body)}</section>"
        for s in sections
    )
    refs_html = "\n".join(f"<li>{html.escape(r)}</li>" for r in references)

    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        f"<title>{html.escape(title)}</title>\n"
        "<style>\n"
        f"body {{ font-family: {font}, serif; font-size: {size}pt; line-height: {line}; "
        "max-width: 800px; margin: 0 auto; padding: 40px; }}\n"
        "h1, h2 { font-weight: 600; }\nblockquote { margin: 8px 0; padding: 4px 12px; "
        "border-left: 3px solid #999; color: #444; }\n"
        "section { margin-bottom: 1.5em; }\n"
        "</style>\n</head>\n<body>\n"
        f"<h1>{html.escape(title)}</h1>\n"
        f"<p class=\"authors\">{authors_html}</p>\n"
        f"<h2>Abstract</h2><p>{html.escape(abstract)}</p>\n"
        f"{sections_html}\n"
        f"<section><h2>AI Use Disclosure</h2><p>{html.escape(ai_disclosure)}</p></section>\n"
        "<section><h2>References</h2><ol>\n" + refs_html + "\n</ol></section>\n"
        "</body>\n</html>\n"
    )


def build_manifest(
    *,
    journal: str,
    title: str,
    authors: list[str],
    figure_count: int,
    ai_disclosure: str,
) -> dict[str, Any]:
    return {
        "journal": journal,
        "title": title,
        "authors": authors,
        "figure_count": figure_count,
        "ai_disclosure": ai_disclosure,
        "reference_style": "author-year",  # overridden by style when available
    }
