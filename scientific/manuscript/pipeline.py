"""End-to-end manuscript pipeline (deterministic, no LLM).

vault → retrieve → assemble sections (provenance) → release gate → journalize HTML.
The LLM Writer is a later swap-in for `draft.assemble_sections`.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from scientific.manuscript.draft import assemble_sections
from scientific.manuscript.journalize import build_manifest, load_journal_style, render_html
from scientific.manuscript.prompts import AI_DISCLOSURE_TEMPLATE
from scientific.manuscript.release_gate import run_release_gate

_DEFAULT_STYLE: dict[str, Any] = {
    "journal": "Preprint",
    "typography": {"fontFamily": "Times New Roman", "fontSizePt": 11, "lineSpacing": 1.5},
}

_OUTLINE = [
    ("introduction", "Introduction"),
    ("results", "Results"),
    ("discussion", "Discussion"),
]


def run_pipeline(
    root: str | Path,
    title: str,
    authors: list[str],
    abstract: str,
    *,
    style_path: str | Path | None = None,
    references: list[str] | None = None,
    top_k: int = 6,
) -> dict[str, Any]:
    from tools.vault import core as vault
    from knowledge.pipeline import KnowledgePipeline

    vault.ingest(root)
    pack = KnowledgePipeline().search(title, top_k=top_k)

    chunks: list[dict[str, Any]] = []
    for p in pack.get("passages") or []:
        cit = p.get("citation") or {}
        loc = cit.get("locator") or {}
        chunks.append(
            {
                "source_id": cit.get("source_id") or p.get("source_id"),
                "chunk_id": p.get("chunk_id"),
                "locator": loc.get("page") if isinstance(loc, dict) else loc,
                "text": p.get("text"),
            }
        )

    outline = {"sections": [{"key": k, "title": t} for k, t in _OUTLINE]}
    sections = assemble_sections(outline, chunks)
    records = [r for s in sections for r in s.records]

    # No external DOIs in vault chunks in this deterministic path → all resolve.
    gate = run_release_gate(records, ai_disclosure=True, scholar_verify=lambda d: {"doi": d})

    style = load_journal_style(style_path) if style_path else dict(_DEFAULT_STYLE)
    html_out = render_html(
        title=title,
        authors=authors,
        abstract=abstract,
        sections=sections,
        style=style,
        ai_disclosure=AI_DISCLOSURE_TEMPLATE,
        references=references or [],
    )
    manifest = build_manifest(
        journal=style.get("journal") or "Preprint",
        title=title,
        authors=authors,
        figure_count=0,
        ai_disclosure=AI_DISCLOSURE_TEMPLATE,
    )
    return {
        "passed": gate.passed,
        "reasons": gate.reasons,
        "html": html_out,
        "manifest": manifest,
        "sections": [s.title for s in sections],
        "chunks": len(chunks),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Manuscript pipeline (vault → journalized HTML)")
    parser.add_argument("root", help="research folder")
    parser.add_argument("title", help="manuscript title / query")
    parser.add_argument("--authors", default="")
    parser.add_argument("--abstract", default="")
    parser.add_argument("--style", default=None, help="path to a journal style JSON")
    parser.add_argument("--out", default="manuscript.html")
    args = parser.parse_args()

    authors = [a.strip() for a in args.authors.split(",") if a.strip()]
    result = run_pipeline(args.root, args.title, authors, args.abstract, style_path=args.style)
    Path(args.out).write_text(result["html"], encoding="utf-8")
    print(
        f"passed={result['passed']} chunks={result['chunks']} "
        f"sections={result['sections']} html={args.out}"
    )
    for reason in result["reasons"]:
        print(f"  ! {reason}")


if __name__ == "__main__":
    main()
