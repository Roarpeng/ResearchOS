"""Deterministic manuscript section assembler (Markdown intermediate + provenance).

The LLM Writer fills this skeleton with prose; this module guarantees every
section carries source-linked provenance records (ADR-0010).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from scientific.manuscript.provenance.record import ProvenanceRecord, SourceRef

DEFAULT_SECTIONS = [
    ("introduction", "Introduction"),
    ("materials", "Materials and Methods"),
    ("results", "Results"),
    ("discussion", "Discussion"),
    ("conclusion", "Conclusion"),
]


@dataclass
class DraftSection:
    key: str
    title: str
    body: str
    records: list[ProvenanceRecord] = field(default_factory=list)


def assemble_sections(
    outline: dict,
    chunks: list[dict],
    created_at: str = "2026-09-06T00:00:00Z",
) -> list[DraftSection]:
    """Build a Markdown section skeleton with per-source provenance records."""
    spec = outline.get("sections") or [{"key": k, "title": t} for k, t in DEFAULT_SECTIONS]
    sections: list[DraftSection] = []
    for s in spec:
        key = s.get("key") or "section"
        title = s.get("title") or key
        relevant = [c for c in chunks if (c.get("section") or "") == key] or chunks
        lines = [f"## {title}", ""]
        records: list[ProvenanceRecord] = []
        for i, c in enumerate(relevant[:3], 1):
            text = str(c.get("text") or "")[:200]
            lines.append(f"> [{i}] {text}")
            records.append(
                ProvenanceRecord(
                    claim_id=f"{key}:{i}",
                    claim_text=text,
                    created_at=created_at,
                    sources=[
                        SourceRef(
                            source_id=str(c.get("source_id") or ""),
                            chunk_ids=[str(c.get("chunk_id") or "")],
                            locator=str(c.get("locator") or "") or None,
                            quote=text[:80],
                        )
                    ],
                )
            )
        lines.append("")
        sections.append(
            DraftSection(key=key, title=title, body="\n".join(lines), records=records)
        )
    return sections
