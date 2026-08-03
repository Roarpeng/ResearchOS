"""Document parser router — Docling / MarkItDown / Unstructured with plain fallback."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable

from knowledge.models import ParseBlock, ParseIR, ParsePage, new_id, utc_now

logger = logging.getLogger("researchos.knowledge.parsers")

ParserFn = Callable[[bytes, str, str], ParseIR]


def detect_extension(filename: str | None, mime_type: str | None = None) -> str:
    if filename and "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    mime = (mime_type or "").lower()
    mapping = {
        "application/pdf": "pdf",
        "text/html": "html",
        "text/markdown": "md",
        "text/plain": "txt",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
        "application/vnd.ms-powerpoint": "ppt",
    }
    return mapping.get(mime, "txt")


def suggest_parser(extension: str) -> str:
    ext = extension.lower().lstrip(".")
    if ext == "pdf":
        return "docling"
    if ext in {"pptx", "ppt"}:
        return "markitdown"
    if ext in {"html", "htm"}:
        return "unstructured"
    if ext in {"md", "txt", "markdown"}:
        return "plaintext"
    return "unstructured"


def _ir_from_markdown(
    markdown: str,
    *,
    doc_id: str,
    parser_name: str,
    parser_version: str = "mvp",
    source_file: str | None = None,
    warnings: list[str] | None = None,
) -> ParseIR:
    pages: list[ParsePage] = []
    blocks: list[ParseBlock] = []
    paragraph = 0
    page_no = 1
    for line in markdown.splitlines():
        raw = line.rstrip()
        if not raw.strip():
            continue
        paragraph += 1
        heading = re.match(r"^(#{1,6})\s+(.*)$", raw)
        if heading:
            level = len(heading.group(1))
            blocks.append(
                ParseBlock(
                    id=new_id("b"),
                    type="heading",
                    level=level,
                    text=heading.group(2).strip(),
                    paragraph=paragraph,
                )
            )
            continue
        if raw.lstrip().startswith("|") and "|" in raw[1:]:
            blocks.append(
                ParseBlock(
                    id=new_id("b"),
                    type="table",
                    text=raw,
                    paragraph=paragraph,
                )
            )
            continue
        lower = raw.lower()
        if lower.startswith("q:") or lower.startswith("问："):
            blocks.append(
                ParseBlock(id=new_id("b"), type="faq_q", text=raw, paragraph=paragraph)
            )
            continue
        if lower.startswith("a:") or lower.startswith("答："):
            blocks.append(
                ParseBlock(id=new_id("b"), type="faq_a", text=raw, paragraph=paragraph)
            )
            continue
        blocks.append(
            ParseBlock(id=new_id("b"), type="paragraph", text=raw, paragraph=paragraph)
        )
    # Group into pages by form-feed or ~80 blocks heuristic
    if not blocks:
        blocks = [ParseBlock(id=new_id("b"), type="paragraph", text=markdown or "", paragraph=1)]
    chunk_size = 80
    for i in range(0, len(blocks), chunk_size):
        pages.append(ParsePage(page=page_no, blocks=blocks[i : i + chunk_size]))
        page_no += 1
    return ParseIR(
        doc_id=doc_id,
        parser={"name": parser_name, "version": parser_version},
        pages=pages,
        markdown=markdown,
        warnings=warnings or [],
        source_file=source_file,
        timestamp=utc_now(),
    )


def _decode_bytes(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def parse_plaintext(data: bytes, doc_id: str, source_file: str | None = None) -> ParseIR:
    text = _decode_bytes(data)
    return _ir_from_markdown(
        text,
        doc_id=doc_id,
        parser_name="plaintext",
        source_file=source_file,
    )


def parse_markitdown(data: bytes, doc_id: str, source_file: str | None = None) -> ParseIR:
    """Prefer MarkItDown when installed; otherwise plain-text / binary fallback."""
    warnings: list[str] = []
    try:
        from markitdown import MarkItDown  # type: ignore[import-not-found]

        import tempfile

        suffix = Path(source_file or "doc.bin").suffix or ".bin"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            tmp.write(data)
            tmp.flush()
            md = MarkItDown()
            result = md.convert(tmp.name)
            text = getattr(result, "text_content", None) or str(result)
        return _ir_from_markdown(
            text,
            doc_id=doc_id,
            parser_name="markitdown",
            source_file=source_file,
            warnings=warnings,
        )
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"markitdown_unavailable:{exc}")
        logger.info("MarkItDown fallback to plaintext: %s", exc)
        ir = parse_plaintext(data, doc_id, source_file=source_file)
        ir.parser = {"name": "plaintext", "version": "mvp"}
        ir.warnings.extend(warnings)
        return ir


def parse_docling(data: bytes, doc_id: str, source_file: str | None = None) -> ParseIR:
    """Optional Docling stub — falls back to plaintext/markitdown."""
    warnings = ["docling_stub_fallback"]
    try:
        import docling  # noqa: F401  # type: ignore[import-not-found]

        warnings.append("docling_import_ok_but_adapter_not_wired")
    except Exception:
        pass
    ir = parse_markitdown(data, doc_id, source_file=source_file)
    ir.parser = {"name": "docling-fallback", "version": "mvp"}
    ir.warnings = warnings + ir.warnings
    return ir


def parse_unstructured(data: bytes, doc_id: str, source_file: str | None = None) -> ParseIR:
    """Optional Unstructured stub — falls back to HTML strip / plaintext."""
    warnings = ["unstructured_stub_fallback"]
    text = _decode_bytes(data)
    if "<html" in text.lower() or "<body" in text.lower():
        text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
        text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
        text = re.sub(r"(?is)<nav.*?>.*?</nav>", " ", text)
        text = re.sub(r"(?is)<[^>]+>", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text).strip()
    ir = _ir_from_markdown(
        text,
        doc_id=doc_id,
        parser_name="unstructured-fallback",
        source_file=source_file,
        warnings=warnings,
    )
    return ir


_PARSERS: dict[str, ParserFn] = {
    "plaintext": lambda data, doc_id, src: parse_plaintext(data, doc_id, src),
    "markitdown": lambda data, doc_id, src: parse_markitdown(data, doc_id, src),
    "docling": lambda data, doc_id, src: parse_docling(data, doc_id, src),
    "unstructured": lambda data, doc_id, src: parse_unstructured(data, doc_id, src),
}


def route_parser(extension: str) -> str:
    return suggest_parser(extension)


def parse_document(
    data: bytes,
    *,
    doc_id: str,
    filename: str | None = None,
    mime_type: str | None = None,
    parser: str = "auto",
) -> ParseIR:
    ext = detect_extension(filename, mime_type)
    name = route_parser(ext) if parser == "auto" else parser
    fn = _PARSERS.get(name) or _PARSERS["unstructured"]
    ir = fn(data, doc_id, filename or f"document.{ext}")
    if not ir.markdown.strip() and data:
        # Last-resort empty content recovery
        ir = parse_plaintext(data, doc_id, filename)
        ir.warnings.append("empty_primary_parser_recovered_plaintext")
    return ir


def list_parsers() -> list[dict[str, str]]:
    return [
        {"name": "docling", "status": "optional_stub"},
        {"name": "markitdown", "status": "optional"},
        {"name": "unstructured", "status": "optional_stub"},
        {"name": "plaintext", "status": "builtin"},
    ]
