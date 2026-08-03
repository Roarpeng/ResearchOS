"""Markdown → PDF (Typst) / DOCX (Pandoc) with graceful fallbacks."""

from __future__ import annotations

import hashlib
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
