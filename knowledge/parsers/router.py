"""Document parser router — Docling / Unstructured / MarkItDown with text fallback.

Routing follows docs/knowledge/02-document-parser-router.md. Rich formats
(pdf/html/docx) resolve through the fallback chain
Docling -> Unstructured -> markitdown -> text; md/txt pass straight to the
text engine. ``PARSER_ENGINE`` (or the ``parser=`` argument) forces the first
engine but keeps the remaining chain as a safety net.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Callable

from knowledge.models import ParseBlock, ParseIR, ParsePage, new_id, utc_now

logger = logging.getLogger("researchos.knowledge.parsers")

ParserFn = Callable[[bytes, str, str], ParseIR]

ENGINE_TEXT = "text"
ENGINE_DOCLING = "docling"
ENGINE_UNSTRUCTURED = "unstructured"
ENGINE_MARKITDOWN = "markitdown"

# docs/knowledge/02: rich-format fallback order is Docling -> Unstructured -> markitdown -> text.
_ROUTE_CHAIN: dict[str, list[str]] = {
    "pdf": [ENGINE_DOCLING, ENGINE_UNSTRUCTURED, ENGINE_MARKITDOWN, ENGINE_TEXT],
    "html": [ENGINE_DOCLING, ENGINE_UNSTRUCTURED, ENGINE_MARKITDOWN, ENGINE_TEXT],
    "htm": [ENGINE_DOCLING, ENGINE_UNSTRUCTURED, ENGINE_MARKITDOWN, ENGINE_TEXT],
    "docx": [ENGINE_DOCLING, ENGINE_UNSTRUCTURED, ENGINE_MARKITDOWN, ENGINE_TEXT],
    "pptx": [ENGINE_MARKITDOWN, ENGINE_UNSTRUCTURED, ENGINE_DOCLING, ENGINE_TEXT],
    "ppt": [ENGINE_MARKITDOWN, ENGINE_UNSTRUCTURED, ENGINE_DOCLING, ENGINE_TEXT],
    "md": [ENGINE_TEXT],
    "txt": [ENGINE_TEXT],
    "markdown": [ENGINE_TEXT],
}
# Unknown / unlisted types fall back to Unstructured per docs/02.
_DEFAULT_CHAIN = [ENGINE_UNSTRUCTURED, ENGINE_DOCLING, ENGINE_MARKITDOWN, ENGINE_TEXT]

_ENGINE_ALIASES = {
    "text": ENGINE_TEXT,
    "plaintext": ENGINE_TEXT,
    "txt": ENGINE_TEXT,
    "docling": ENGINE_DOCLING,
    "unstructured": ENGINE_UNSTRUCTURED,
    "markitdown": ENGINE_MARKITDOWN,
    "md": ENGINE_MARKITDOWN,
}


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
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/msword": "doc",
    }
    return mapping.get(mime, "txt")


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _err(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def _dist_version(dist: str) -> str | None:
    try:
        from importlib import metadata

        return metadata.version(dist)
    except Exception:  # noqa: BLE001
        return None


def _write_temp(data: bytes, suffix: str) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(data)
        tmp.flush()
        return tmp.name
    finally:
        tmp.close()


def _unlink(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def _decode_bytes(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


_HTML_HINT = re.compile(r"(?is)<\s*(html|body|head|div|span|table|p|h[1-6]|a|ul|ol|li|section|article)\b[^>]*>")
_HTML_BLOCK = re.compile(r"(?is)<(script|style|nav|noscript|template)\b[^>]*>.*?</\1\s*>")
_HTML_TAG = re.compile(r"(?is)<[^>]+>")


def _looks_like_html(text: str) -> bool:
    return bool(_HTML_HINT.search(text))


def _strip_html(text: str) -> str:
    """Best-effort HTML noise removal for the text fallback engine."""
    if not _looks_like_html(text):
        return text
    text = _HTML_BLOCK.sub(" ", text)
    text = _HTML_TAG.sub("\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _markdown_blocks(markdown: str) -> list[ParseBlock]:
    """Split markdown lines into typed ParseBlocks (headings / tables / FAQ / text)."""
    blocks: list[ParseBlock] = []
    paragraph = 0
    for line in markdown.splitlines():
        raw = line.rstrip()
        if not raw.strip():
            continue
        paragraph += 1
        heading = re.match(r"^(#{1,6})\s+(.*)$", raw)
        if heading:
            blocks.append(
                ParseBlock(
                    id=new_id("b"),
                    type="heading",
                    level=len(heading.group(1)),
                    text=heading.group(2).strip(),
                    paragraph=paragraph,
                )
            )
            continue
        if raw.lstrip().startswith("|") and "|" in raw[1:]:
            blocks.append(ParseBlock(id=new_id("b"), type="table", text=raw, paragraph=paragraph))
            continue
        lower = raw.lower()
        if lower.startswith("q:") or lower.startswith("问："):
            blocks.append(ParseBlock(id=new_id("b"), type="faq_q", text=raw, paragraph=paragraph))
            continue
        if lower.startswith("a:") or lower.startswith("答："):
            blocks.append(ParseBlock(id=new_id("b"), type="faq_a", text=raw, paragraph=paragraph))
            continue
        blocks.append(ParseBlock(id=new_id("b"), type="paragraph", text=raw, paragraph=paragraph))
    if not blocks:
        blocks = [ParseBlock(id=new_id("b"), type="paragraph", text=markdown or "", paragraph=1)]
    return blocks


def _pages_from_blocks(blocks: list[ParseBlock], chunk_size: int = 80) -> list[ParsePage]:
    pages: list[ParsePage] = []
    page_no = 1
    for i in range(0, len(blocks), chunk_size):
        pages.append(ParsePage(page=page_no, blocks=blocks[i : i + chunk_size]))
        page_no += 1
    return pages


def _parser_meta(
    name: str,
    *,
    version: str | None = None,
    engine_selected: str | None = None,
    fallback_chain: list[str] | None = None,
) -> dict[str, str]:
    meta: dict[str, str] = {"name": name}
    if version:
        meta["version"] = str(version)
    meta["engine_selected"] = engine_selected or name
    meta["fallback_chain"] = ",".join(fallback_chain or [name])
    return meta


def _classify_element(category: str) -> tuple[str, int | None]:
    """Map an Unstructured element category to a ParseBlock type."""
    cat = category.strip().lower()
    if cat == "title":
        return "heading", 1
    if cat in {"headline", "sectionheader", "section_header", "subtitle", "subheader"}:
        return "heading", 2
    if cat == "header":
        return "header", None
    if cat == "footer":
        return "footer", None
    if cat in {"table", "tablehtml", "tabletext"}:
        return "table", None
    if cat in {"listitem", "list_item"}:
        return "list", None
    if cat in {"code", "codesnippet"}:
        return "code", None
    if cat in {"figurecaption", "figure_caption"}:
        return "figure_caption", None
    return "paragraph", None


def _element_page(el: Any) -> int:
    meta = getattr(el, "metadata", None)
    if meta is not None:
        for attr in ("page_number", "page", "page_num"):
            try:
                v = getattr(meta, attr, None)
            except Exception:  # noqa: BLE001
                v = None
            if v is not None:
                page = _safe_int(v)
                if page is not None:
                    return page
        if isinstance(meta, dict):
            for key in ("page_number", "page", "page_num"):
                page = _safe_int(meta.get(key))
                if page is not None:
                    return page
    return 1


def _table_data(el: Any) -> dict[str, Any] | None:
    meta = getattr(el, "metadata", None)
    html = None
    if meta is not None:
        html = getattr(meta, "text_as_html", None)
        if html is None and isinstance(meta, dict):
            html = meta.get("text_as_html")
    if html:
        return {"headers": [], "rows": [], "text_as_html": html}
    return None


def _markdown_from_blocks(blocks: list[ParseBlock]) -> str:
    lines: list[str] = []
    for b in blocks:
        text = (b.text or "").rstrip()
        if not text:
            continue
        if b.type == "heading":
            lines.append(f"{'#' * (b.level or 2)} {text}")
        else:
            lines.append(text)
    return "\n\n".join(lines)


def _ir_from_markdown(
    markdown: str,
    *,
    doc_id: str,
    parser_name: str,
    parser_version: str | None = None,
    source_file: str | None = None,
    warnings: list[str] | None = None,
    engine_selected: str | None = None,
    fallback_chain: list[str] | None = None,
    pages: list[ParsePage] | None = None,
) -> ParseIR:
    if pages is None:
        pages = _pages_from_blocks(_markdown_blocks(markdown))
    return ParseIR(
        doc_id=doc_id,
        parser=_parser_meta(
            parser_name,
            version=parser_version,
            engine_selected=engine_selected,
            fallback_chain=fallback_chain,
        ),
        pages=pages,
        markdown=markdown,
        warnings=warnings or [],
        source_file=source_file,
        timestamp=utc_now(),
    )


# --------------------------------------------------------------------------- #
# Text engine (always available)
# --------------------------------------------------------------------------- #
def parse_text(data: bytes, doc_id: str, source_file: str | None = None) -> ParseIR:
    text = _strip_html(_decode_bytes(data))
    return _ir_from_markdown(
        text,
        doc_id=doc_id,
        parser_name=ENGINE_TEXT,
        source_file=source_file,
        engine_selected=ENGINE_TEXT,
        fallback_chain=[ENGINE_TEXT],
    )


def parse_plaintext(data: bytes, doc_id: str, source_file: str | None = None) -> ParseIR:
    """Backward-compatible alias for the text engine."""
    return parse_text(data, doc_id, source_file)


# --------------------------------------------------------------------------- #
# MarkItDown provider (lazy optional dependency)
# --------------------------------------------------------------------------- #
class MarkItDownProvider:
    engine = ENGINE_MARKITDOWN

    def __init__(self) -> None:
        self.available = False
        self.version: str | None = None
        self.error: str | None = None
        self._cls: Any = None
        try:
            from markitdown import MarkItDown  # type: ignore[import-not-found]

            self._cls = MarkItDown
            self.available = True
            self.version = _dist_version("markitdown")
        except Exception as exc:  # noqa: BLE001
            self.error = _err(exc)

    def convert(self, data: bytes, source_file: str | None = None) -> str:
        if not self.available:
            raise RuntimeError(self.error or "markitdown unavailable")
        suffix = Path(source_file or "doc.bin").suffix or ".bin"
        path = _write_temp(data, suffix)
        try:
            result = self._cls().convert(path)
            text = getattr(result, "text_content", None)
            if text is None:
                text = str(result)
            return text or ""
        finally:
            _unlink(path)


# --------------------------------------------------------------------------- #
# Docling provider (lazy optional dependency)
# --------------------------------------------------------------------------- #
class DoclingProvider:
    engine = ENGINE_DOCLING

    def __init__(self) -> None:
        self.available = False
        self.version: str | None = None
        self.error: str | None = None
        self._converter: Any = None
        try:
            from docling.document_converter import DocumentConverter  # type: ignore[import-not-found]

            self._converter = DocumentConverter
            self.available = True
            self.version = _dist_version("docling")
        except Exception as exc:  # noqa: BLE001
            self.error = _err(exc)

    def parse(self, data: bytes, doc_id: str, source_file: str | None = None) -> ParseIR:
        if not self.available:
            raise RuntimeError(self.error or "docling unavailable")
        suffix = Path(source_file or "doc.pdf").suffix or ".pdf"
        path = _write_temp(data, suffix)
        try:
            converter = self._converter()
            result = converter.convert(path)
            doc = getattr(result, "document", None)
            markdown, pages = self._to_markdown_and_pages(doc)
            if not markdown:
                markdown = _decode_bytes(data)
            if not pages:
                pages = _pages_from_blocks(_markdown_blocks(markdown))
            return _ir_from_markdown(
                markdown,
                doc_id=doc_id,
                parser_name=self.engine,
                parser_version=self.version,
                source_file=source_file,
                engine_selected=self.engine,
                fallback_chain=[self.engine],
                pages=pages,
            )
        finally:
            _unlink(path)

    def _to_markdown_and_pages(self, doc: Any) -> tuple[str, list[ParsePage]]:
        if doc is None:
            return "", []
        markdown = ""
        try:
            markdown = doc.export_to_markdown() or ""
        except Exception:  # noqa: BLE001
            try:
                markdown = str(doc)
            except Exception:  # noqa: BLE001
                markdown = ""
        try:
            raw_pages = getattr(doc, "pages", None) or []
        except Exception:  # noqa: BLE001
            raw_pages = []
        items: list[tuple[int, Any]] = []
        if isinstance(raw_pages, dict):
            for key in sorted(raw_pages.keys(), key=lambda k: _safe_int(k) or 0):
                items.append((_safe_int(key) or 1, raw_pages[key]))
        else:
            for idx, page in enumerate(raw_pages, start=1):
                items.append((idx, page))
        pages: list[ParsePage] = []
        for fallback_no, page in items:
            pno = fallback_no
            try:
                pno = _safe_int(getattr(page, "page_no", None)) or fallback_no
            except Exception:  # noqa: BLE001
                pno = fallback_no
            pmd = ""
            try:
                pmd = page.export_to_markdown() or ""
            except Exception:  # noqa: BLE001
                try:
                    pmd = str(page)
                except Exception:  # noqa: BLE001
                    pmd = ""
            pages.append(ParsePage(page=pno, blocks=_markdown_blocks(pmd or "")))
        return markdown, pages


# --------------------------------------------------------------------------- #
# Unstructured provider (lazy optional dependency)
# --------------------------------------------------------------------------- #
class UnstructuredProvider:
    engine = ENGINE_UNSTRUCTURED

    def __init__(self) -> None:
        self.available = False
        self.version: str | None = None
        self.error: str | None = None
        try:
            import unstructured  # noqa: F401

            self.available = True
            self.version = _dist_version("unstructured")
        except Exception as exc:  # noqa: BLE001
            self.error = _err(exc)

    def parse(self, data: bytes, doc_id: str, source_file: str | None = None) -> ParseIR:
        if not self.available:
            raise RuntimeError(self.error or "unstructured unavailable")
        ext = detect_extension(source_file)
        elements = self._partition(data, ext, source_file)
        blocks, pages = self._blocks_from_elements(elements)
        markdown = _markdown_from_blocks(blocks)
        return _ir_from_markdown(
            markdown,
            doc_id=doc_id,
            parser_name=self.engine,
            parser_version=self.version,
            source_file=source_file,
            engine_selected=self.engine,
            fallback_chain=[self.engine],
            pages=pages,
        )

    def _partition(self, data: bytes, ext: str, source_file: str | None) -> Any:
        suffix = Path(source_file or f"doc.{ext or 'html'}").suffix or ".html"
        path = _write_temp(data, suffix)
        try:
            if ext in {"html", "htm"}:
                from unstructured.partition.html import partition_html  # type: ignore[import-not-found]

                try:
                    return partition_html(filename=path)
                except TypeError:
                    text = _decode_bytes(data)
                    try:
                        return partition_html(text=text)
                    except TypeError:
                        return partition_html(html_text=text)
            if ext == "pdf":
                from unstructured.partition.pdf import partition_pdf  # type: ignore[import-not-found]

                return partition_pdf(filename=path)
            from unstructured.partition.auto import partition  # type: ignore[import-not-found]

            return partition(filename=path)
        finally:
            _unlink(path)

    def _blocks_from_elements(self, elements: Any) -> tuple[list[ParseBlock], list[ParsePage]]:
        blocks: list[ParseBlock] = []
        pages: dict[int, list[ParseBlock]] = {}
        for el in elements:
            text = getattr(el, "text", None)
            if text is None:
                text = str(el)
            text = str(text).strip()
            if not text:
                continue
            category = str(getattr(el, "category", "") or "").lower()
            btype, level = _classify_element(category)
            table = _table_data(el) if btype == "table" else None
            pno = _element_page(el)
            blocks.append(
                ParseBlock(
                    id=new_id("b"),
                    type=btype,
                    level=level,
                    text=text,
                    paragraph=len(blocks) + 1,
                    table=table,
                )
            )
            pages.setdefault(pno, []).append(blocks[-1])
        if not blocks:
            blocks = [ParseBlock(id=new_id("b"), type="paragraph", text="", paragraph=1)]
        if not pages:
            pages[1] = blocks
        return blocks, [ParsePage(page=k, blocks=v) for k, v in sorted(pages.items())]


# --------------------------------------------------------------------------- #
# Standalone engine entry points (raise when their optional dep is missing)
# --------------------------------------------------------------------------- #
def parse_markitdown(data: bytes, doc_id: str, source_file: str | None = None) -> ParseIR:
    provider = MarkItDownProvider()
    if not provider.available:
        raise RuntimeError(provider.error or "markitdown unavailable")
    text = provider.convert(data, source_file)
    return _ir_from_markdown(
        text,
        doc_id=doc_id,
        parser_name=ENGINE_MARKITDOWN,
        parser_version=provider.version,
        source_file=source_file,
        engine_selected=ENGINE_MARKITDOWN,
        fallback_chain=[ENGINE_MARKITDOWN],
    )


def parse_docling(data: bytes, doc_id: str, source_file: str | None = None) -> ParseIR:
    return DoclingProvider().parse(data, doc_id, source_file)


def parse_unstructured(data: bytes, doc_id: str, source_file: str | None = None) -> ParseIR:
    return UnstructuredProvider().parse(data, doc_id, source_file)


_ENGINE_FUNCS: dict[str, ParserFn] = {
    ENGINE_TEXT: parse_text,
    ENGINE_MARKITDOWN: parse_markitdown,
    ENGINE_DOCLING: parse_docling,
    ENGINE_UNSTRUCTURED: parse_unstructured,
}


# --------------------------------------------------------------------------- #
# Routing
# --------------------------------------------------------------------------- #
def suggest_parser(extension: str) -> str:
    ext = extension.lower().lstrip(".")
    return _ROUTE_CHAIN.get(ext, _DEFAULT_CHAIN)[0]


def route_parser(extension: str) -> str:
    return suggest_parser(extension)


def _forced_engine(parser_param: str) -> str | None:
    env = os.environ.get("PARSER_ENGINE", "").strip().lower()
    if env and env != "auto":
        return _ENGINE_ALIASES.get(env)
    if parser_param and parser_param != "auto":
        return _ENGINE_ALIASES.get(parser_param.strip().lower())
    return None


def _parse_with_chain(data: bytes, doc_id: str, source_file: str, chain: list[str]) -> ParseIR:
    warnings: list[str] = []
    attempted: list[str] = []
    for engine in chain:
        attempted.append(engine)
        fn = _ENGINE_FUNCS.get(engine)
        if fn is None:
            warnings.append(f"unknown_engine:{engine}")
            continue
        try:
            ir = fn(data, doc_id, source_file)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{engine}_unavailable:{_err(exc)}")
            logger.info("parser engine %s unavailable: %s", engine, exc)
            continue
        if not (ir.markdown or "").strip() and data:
            warnings.append(f"{engine}_empty_result")
            ir = parse_text(data, doc_id, source_file)
            attempted.append(ENGINE_TEXT)
            ir.parser = _parser_meta(
                ir.parser.get("name", ENGINE_TEXT),
                version=ir.parser.get("version"),
                engine_selected=ENGINE_TEXT,
                fallback_chain=attempted,
            )
        else:
            ir.parser = _parser_meta(
                ir.parser.get("name", engine),
                version=ir.parser.get("version"),
                engine_selected=engine,
                fallback_chain=attempted,
            )
        ir.warnings = warnings + list(ir.warnings)
        return ir
    # Defensive floor: the text engine is always last and never raises, but keep a hard stop.
    ir = parse_text(data, doc_id, source_file)
    warnings.append("all_parsers_failed_fell_back_to_text")
    ir.parser = _parser_meta(ENGINE_TEXT, engine_selected=ENGINE_TEXT, fallback_chain=attempted)
    ir.warnings = warnings + list(ir.warnings)
    return ir


def parse_document(
    data: bytes,
    *,
    doc_id: str,
    filename: str | None = None,
    mime_type: str | None = None,
    parser: str = "auto",
) -> ParseIR:
    ext = detect_extension(filename, mime_type)
    source_file = filename or f"document.{ext}"
    forced = _forced_engine(parser)
    base_chain = _ROUTE_CHAIN.get(ext, _DEFAULT_CHAIN)
    if forced:
        chain = [forced] + [e for e in base_chain if e != forced]
    else:
        chain = list(base_chain)
    return _parse_with_chain(data, doc_id, source_file, chain)


def list_parsers() -> list[dict[str, str]]:
    docling = DoclingProvider()
    unstructured = UnstructuredProvider()
    markitdown = MarkItDownProvider()
    return [
        {
            "name": ENGINE_DOCLING,
            "status": "available" if docling.available else "unavailable",
            "version": docling.version or "",
        },
        {
            "name": ENGINE_UNSTRUCTURED,
            "status": "available" if unstructured.available else "unavailable",
            "version": unstructured.version or "",
        },
        {
            "name": ENGINE_MARKITDOWN,
            "status": "available" if markitdown.available else "unavailable",
            "version": markitdown.version or "",
        },
        {"name": ENGINE_TEXT, "status": "builtin", "version": ""},
    ]
