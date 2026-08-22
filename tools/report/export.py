"""Markdown → PDF (Typst) / DOCX (Pandoc) with graceful fallbacks."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Literal


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _typst_available() -> bool:
    return shutil.which("typst") is not None


def _pandoc_available() -> bool:
    return shutil.which("pandoc") is not None


def _markdown_to_typst(markdown: str, title: str) -> str:
    # Minimal Typst wrapper; preserves body as raw text blocks.
    escaped_title = title.replace("\\", "\\\\").replace('"', '\\"')
    body = markdown.replace("\\", "\\\\")
    return f"""#set document(title: "{escaped_title}")
#set page(margin: 2cm)
#set text(font: "New Computer Modern", size: 11pt)
#heading(level: 1)[{escaped_title}]

#let md = ```
{body}
```
#md
"""


def markdown_to_pdf(
    markdown: str,
    *,
    output_dir: str | Path,
    title: str = "ResearchOS Report",
    basename: str = "report",
) -> dict[str, Any]:
    """Render Markdown to PDF via Typst when installed; else write .md + note."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    md_path = out / f"{basename}.md"
    md_path.write_text(markdown, encoding="utf-8")

    if not _typst_available():
        note = out / f"{basename}.EXPORT_NOTE.txt"
        note.write_text(
            "typst binary not found; wrote Markdown only. Install typst to enable PDF export.\n",
            encoding="utf-8",
        )
        data = markdown.encode("utf-8")
        return {
            "ok": True,
            "format": "markdown",
            "engine_used": "none",
            "path": str(md_path),
            "bytes": len(data),
            "checksum": _sha256(data),
            "warnings": ["typst not installed; PDF skipped"],
        }

    typ_path = out / f"{basename}.typ"
    pdf_path = out / f"{basename}.pdf"
    typ_path.write_text(_markdown_to_typst(markdown, title), encoding="utf-8")
    try:
        subprocess.run(
            ["typst", "compile", str(typ_path), str(pdf_path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        return {
            "ok": False,
            "format": "pdf",
            "engine_used": "typst",
            "path": str(md_path),
            "error": exc.stderr or str(exc),
            "warnings": ["typst compile failed; Markdown retained"],
        }

    data = pdf_path.read_bytes()
    return {
        "ok": True,
        "format": "pdf",
        "engine_used": "typst",
        "path": str(pdf_path),
        "markdown_path": str(md_path),
        "bytes": len(data),
        "checksum": _sha256(data),
        "warnings": [],
    }


def markdown_to_docx(
    markdown: str,
    *,
    output_dir: str | Path,
    basename: str = "report",
) -> dict[str, Any]:
    """Optional Pandoc DOCX export."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    md_path = out / f"{basename}.md"
    if not md_path.exists():
        md_path.write_text(markdown, encoding="utf-8")

    if not _pandoc_available():
        return {
            "ok": False,
            "format": "docx",
            "engine_used": "none",
            "path": str(md_path),
            "error": "pandoc not installed",
            "warnings": ["DOCX skipped"],
        }

    docx_path = out / f"{basename}.docx"
    try:
        subprocess.run(
            ["pandoc", str(md_path), "-o", str(docx_path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        return {
            "ok": False,
            "format": "docx",
            "engine_used": "pandoc",
            "error": exc.stderr or str(exc),
            "warnings": ["pandoc failed"],
        }

    data = docx_path.read_bytes()
    return {
        "ok": True,
        "format": "docx",
        "engine_used": "pandoc",
        "path": str(docx_path),
        "bytes": len(data),
        "checksum": _sha256(data),
        "warnings": [],
    }


def export_report(
    markdown: str,
    *,
    format: Literal["pdf", "docx", "markdown"] = "pdf",
    engine: Literal["auto", "typst", "pandoc"] = "auto",
    title: str = "ResearchOS Report",
    output_dir: str | Path | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Facade used by MCP report.export."""
    base = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="researchos_report_"))
    basename = f"report_{task_id}" if task_id else "report"

    if format == "markdown":
        path = base / f"{basename}.md"
        path.write_text(markdown, encoding="utf-8")
        data = markdown.encode("utf-8")
        return {
            "ok": True,
            "artifact_id": f"art_{basename}",
            "format": "markdown",
            "engine_used": "none",
            "path": str(path),
            "bytes": len(data),
            "checksum": _sha256(data),
            "warnings": [],
        }

    if format == "docx" or (format == "pdf" and engine == "pandoc"):
        if format == "docx":
            result = markdown_to_docx(markdown, output_dir=base, basename=basename)
        else:
            # pandoc pdf path is optional; fall back to markdown note
            result = markdown_to_docx(markdown, output_dir=base, basename=basename)
            result = {**result, "warnings": result.get("warnings", []) + ["pdf via pandoc not configured"]}
        result["artifact_id"] = f"art_{basename}"
        return result

    # default pdf via typst
    result = markdown_to_pdf(markdown, output_dir=base, title=title, basename=basename)
    result["artifact_id"] = f"art_{basename}"
    return result


_MARKER_RE = re.compile(r"\[\^(?P<id>[A-Za-z0-9_.:-]+)\]|\[citation:(?P<bid>[A-Za-z0-9_.:-]+)\]")
_FOOTNOTE_DEF_RE = re.compile(r"^\[\^[A-Za-z0-9_.:-]+\]:", re.MULTILINE)
_REQUIRED_PROVENANCE = ("url", "source_id", "source", "locator")


def validate_citations(
    markdown: str,
    citations: list[dict[str, Any]] | None = None,
    *,
    on_policy: Literal["strict", "warn"] = "strict",
) -> dict[str, Any]:
    """Pre-export citation completeness check (docs/mcp/06-report-export-tools.md).

    Every in-text marker must resolve to a citation entry; every citation must
    carry minimal provenance (url / source_id / source / locator).
    """
    citations = citations or []
    by_id: dict[str, dict[str, Any]] = {
        str(c.get("id")): c for c in citations if c.get("id")
    }
    body = _FOOTNOTE_DEF_RE.sub("", markdown or "")
    markers: list[str] = []
    for match in _MARKER_RE.finditer(body):
        cid = match.group("id") or match.group("bid") or ""
        if cid:
            markers.append(cid)

    unresolved = sorted({m for m in markers if m not in by_id})
    invalid: list[dict[str, Any]] = []
    referenced: set[str] = set()
    for cid in markers:
        cit = by_id.get(cid)
        if cit is None:
            continue
        referenced.add(cid)
        if not any(str(cit.get(k) or "").strip() for k in _REQUIRED_PROVENANCE):
            invalid.append({"id": cid, "reason": "missing_provenance"})

    unreferenced = sorted(set(by_id) - referenced)
    ok = not unresolved and not invalid
    result: dict[str, Any] = {
        "ok": ok,
        "on_policy": on_policy,
        "citation_stats": {
            "total": len(citations),
            "markers": len(markers),
            "unresolved_markers": len(unresolved),
            "invalid_provenance": len(invalid),
            "unreferenced_citations": len(unreferenced),
        },
    }
    if unresolved:
        result["unresolved"] = unresolved[:64]
    if invalid:
        result["invalid"] = invalid[:64]
    if unreferenced:
        result["unreferenced"] = unreferenced[:64]
    if not ok and on_policy == "strict":
        result["error"] = "citation_incomplete"
    return result


def report_preview(
    markdown: str,
    *,
    title: str = "ResearchOS Report",
    citations: list[dict[str, Any]] | None = None,
    head_chars: int = 1200,
) -> dict[str, Any]:
    """Side-effect-free short preview (docs/mcp/06: 可无 PDF)."""
    text = markdown or ""
    sections = [ln for ln in text.splitlines() if ln.startswith("## ")]
    validation = validate_citations(text, citations)
    return {
        "ok": True,
        "title": title,
        "chars": len(text),
        "head": text[: max(0, int(head_chars))],
        "sections": len(sections),
        "section_titles": sections[:24],
        "citation_stats": validation["citation_stats"],
        "citation_check_ok": validation["ok"],
    }
