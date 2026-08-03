"""Structure-aware semantic chunking."""

from __future__ import annotations

import hashlib
import re
from typing import Iterable

from knowledge.models import Chunk, Locator, ParseBlock, ParseIR, SectionType, new_id
from knowledge.settings import KnowledgeSettings, get_settings

_HEADING_SECTION_HINTS: list[tuple[re.Pattern[str], SectionType]] = [
    (re.compile(r"(规格|specification|specs?)", re.I), "specification"),
    (re.compile(r"(参数|parameter|params?)", re.I), "parameter"),
    (re.compile(r"(faq|常见问题|问答)", re.I), "faq"),
    (re.compile(r"(评测|评价|review|用户反馈|差评|痛点)", re.I), "review"),
    (re.compile(r"(新闻|news|公告)", re.I), "news"),
]


def _classify_heading(text: str) -> SectionType:
    for pattern, section in _HEADING_SECTION_HINTS:
        if pattern.search(text):
            return section
    return "narrative"


def _classify_block(block: ParseBlock, current: SectionType) -> SectionType:
    if block.type == "heading":
        hinted = _classify_heading(block.text)
        if hinted != "narrative":
            return hinted
        # Level-1 headings without keyword hints are titles; deeper stay narrative labels.
        if (block.level or 3) <= 1:
            return "title"
        return "narrative"
    if block.type == "table":
        return "table"
    if block.type in {"faq_q", "faq_a"}:
        return "faq"
    if block.type == "review_body":
        return "review"
    if current == "title":
        return "narrative"
    return current


def _hash_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_oversized(
    text: str,
    *,
    soft_max: int,
    hard_max: int,
) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= soft_max:
        return [text]
    parts: list[str] = []
    # Prefer paragraph / sentence boundaries
    paragraphs = re.split(r"\n{2,}", text)
    buf = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(buf) + len(para) + 2 <= soft_max:
            buf = f"{buf}\n\n{para}".strip()
            continue
        if buf:
            parts.append(buf)
        if len(para) <= soft_max:
            buf = para
        else:
            # sentence split
            sentences = re.split(r"(?<=[。！？.!?])\s*", para)
            buf = ""
            for sent in sentences:
                if not sent:
                    continue
                if len(buf) + len(sent) + 1 <= soft_max:
                    buf = f"{buf} {sent}".strip()
                else:
                    if buf:
                        parts.append(buf)
                    if len(sent) > hard_max:
                        for i in range(0, len(sent), hard_max):
                            parts.append(sent[i : i + hard_max])
                        buf = ""
                    else:
                        buf = sent
            if buf:
                parts.append(buf)
                buf = ""
    if buf:
        parts.append(buf)
    return parts or [text[:hard_max]]


def _flush_group(
    group: list[tuple[ParseBlock, int]],
    *,
    section_type: SectionType,
    section_path: list[str],
    ir: ParseIR,
    workspace_id: str,
    soft_max: int,
    hard_max: int,
) -> list[Chunk]:
    if not group:
        return []
    text = "\n".join(b.text for b, _ in group).strip()
    if not text:
        return []
    page = group[0][1]
    paragraph = group[0][0].paragraph
    pieces = _split_oversized(text, soft_max=soft_max, hard_max=hard_max)
    parent_section_id = new_id("sec")
    parent_chunk_id = new_id("chk") if len(pieces) > 1 else None
    chunks: list[Chunk] = []
    for idx, piece in enumerate(pieces):
        chunk_id = parent_chunk_id if idx == 0 and parent_chunk_id else new_id("chk")
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                doc_id=ir.doc_id,
                workspace_id=workspace_id,
                source_id=ir.doc_id,
                section_type=section_type if section_type != "title" or idx == 0 else "narrative",
                section_path=list(section_path),
                text=piece,
                locator=Locator(
                    page=page,
                    paragraph=paragraph,
                    url=ir.url,
                    offset_start=None,
                    offset_end=None,
                ),
                source_file=ir.source_file,
                object_key=ir.object_key,
                url=ir.url,
                timestamp=ir.timestamp,
                language=ir.language,
                parser=(ir.parser or {}).get("name"),
                parent_chunk_id=parent_chunk_id if idx > 0 else None,
                parent_section_id=parent_section_id if len(pieces) > 1 else None,
                content_hash=_hash_text(piece),
            )
        )
    return chunks


def chunk_parse_ir(
    ir: ParseIR,
    *,
    workspace_id: str = "default",
    settings: KnowledgeSettings | None = None,
) -> list[Chunk]:
    """Chunk a Parse IR using structural signals; fallback windows only when needed."""
    cfg = settings or get_settings()
    soft_max = cfg.chunk_soft_max_chars
    hard_max = cfg.chunk_hard_max_chars

    chunks: list[Chunk] = []
    section_path: list[str] = []
    current_type: SectionType = "narrative"
    group: list[tuple[ParseBlock, int]] = []
    faq_buf: list[tuple[ParseBlock, int]] = []

    def flush(section_type: SectionType) -> None:
        nonlocal group
        chunks.extend(
            _flush_group(
                group,
                section_type=section_type,
                section_path=section_path,
                ir=ir,
                workspace_id=workspace_id,
                soft_max=soft_max,
                hard_max=hard_max,
            )
        )
        group = []

    has_structure = False
    for page in ir.pages:
        for block in page.blocks:
            if block.type in {"heading", "table", "faq_q", "faq_a", "review_body"}:
                has_structure = True
            st = _classify_block(block, current_type)
            if block.type == "heading":
                flush(current_type)
                if faq_buf:
                    chunks.extend(
                        _flush_group(
                            faq_buf,
                            section_type="faq",
                            section_path=section_path,
                            ir=ir,
                            workspace_id=workspace_id,
                            soft_max=soft_max,
                            hard_max=hard_max,
                        )
                    )
                    faq_buf = []
                level = block.level or 2
                section_path = section_path[: max(level - 1, 0)] + [block.text]
                current_type = st
                group = [(block, page.page)]
                flush(current_type)
                current_type = "narrative" if st == "title" else st
                continue

            if block.type in {"faq_q", "faq_a"} or current_type == "faq":
                flush(current_type)
                faq_buf.append((block, page.page))
                if block.type == "faq_a" or (
                    faq_buf and faq_buf[-1][0].type == "faq_a"
                ):
                    # flush Q+A pair when answer arrives
                    if any(b.type == "faq_q" for b, _ in faq_buf) and any(
                        b.type == "faq_a" for b, _ in faq_buf
                    ):
                        chunks.extend(
                            _flush_group(
                                faq_buf,
                                section_type="faq",
                                section_path=section_path,
                                ir=ir,
                                workspace_id=workspace_id,
                                soft_max=soft_max,
                                hard_max=hard_max,
                            )
                        )
                        faq_buf = []
                current_type = "faq"
                continue

            if st != current_type and group:
                flush(current_type)
                current_type = st
            elif st != current_type:
                current_type = st
            group.append((block, page.page))

    if faq_buf:
        chunks.extend(
            _flush_group(
                faq_buf,
                section_type="faq",
                section_path=section_path,
                ir=ir,
                workspace_id=workspace_id,
                soft_max=soft_max,
                hard_max=hard_max,
            )
        )
    flush(current_type)

    if not chunks:
        # Absolute fallback: window the markdown
        text = (ir.markdown or "").strip() or " "
        pieces = _split_oversized(text, soft_max=soft_max, hard_max=hard_max)
        parent_section_id = new_id("sec")
        for i, piece in enumerate(pieces):
            chunks.append(
                Chunk(
                    chunk_id=new_id("chk"),
                    doc_id=ir.doc_id,
                    workspace_id=workspace_id,
                    source_id=ir.doc_id,
                    section_type="fallback_window",
                    section_path=section_path or ["document"],
                    text=piece,
                    locator=Locator(page=1, paragraph=i + 1, url=ir.url),
                    source_file=ir.source_file,
                    object_key=ir.object_key,
                    url=ir.url,
                    timestamp=ir.timestamp,
                    parser=(ir.parser or {}).get("name"),
                    parent_section_id=parent_section_id if len(pieces) > 1 else None,
                    content_hash=_hash_text(piece),
                    metadata={"warning": "fallback_window"},
                )
            )
    elif not has_structure:
        for c in chunks:
            if c.section_type == "narrative":
                c.section_type = "fallback_window"
                c.metadata["warning"] = "unstructured_document"

    return chunks


def chunk_text(
    text: str,
    *,
    doc_id: str,
    source_file: str | None = None,
    workspace_id: str = "default",
    settings: KnowledgeSettings | None = None,
) -> list[Chunk]:
    from knowledge.parsers.router import _ir_from_markdown

    ir = _ir_from_markdown(
        text,
        doc_id=doc_id,
        parser_name="plaintext",
        source_file=source_file,
    )
    return chunk_parse_ir(ir, workspace_id=workspace_id, settings=settings)


def section_type_histogram(chunks: Iterable[Chunk]) -> dict[str, int]:
    hist: dict[str, int] = {}
    for c in chunks:
        hist[c.section_type] = hist.get(c.section_type, 0) + 1
    return hist
