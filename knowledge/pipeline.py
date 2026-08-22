"""Ingestion pipeline: parse → chunk → embed → upsert three channels."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from knowledge.chunking.semantic import chunk_parse_ir
from knowledge.embeddings import active_embed_model
from knowledge.extract.entities import extract_from_chunks
from knowledge.models import IngestResult
from knowledge.parsers.router import parse_document
from knowledge.persist import save_registry
from knowledge.store import StoreRegistry, get_registry

logger = logging.getLogger("researchos.knowledge.pipeline")


class KnowledgePipeline:
    def __init__(self, registry: StoreRegistry | None = None) -> None:
        self.registry = registry or get_registry()

    def ingest_bytes(
        self,
        data: bytes,
        *,
        filename: str | None = None,
        mime_type: str | None = None,
        workspace_id: str | None = None,
        title: str | None = None,
        doc_id: str | None = None,
        url: str | None = None,
    ) -> IngestResult:
        reg = self.registry
        ws = workspace_id or reg.settings.default_workspace_id
        meta = reg.documents.register(
            title=title,
            filename=filename,
            mime_type=mime_type,
            workspace_id=ws,
            url=url,
            doc_id=doc_id,
        )
        meta = reg.documents.put_bytes(meta.doc_id, data, filename=filename)
        reg.documents.update_status(meta.doc_id, "parsing")

        ir = parse_document(
            data,
            doc_id=meta.doc_id,
            filename=filename or meta.source_file,
            mime_type=mime_type or meta.mime_type,
        )
        ir.object_key = meta.object_key
        ir.source_file = meta.source_file
        ir.url = url or meta.url
        reg.documents.update_status(
            meta.doc_id,
            "chunking",
            parser_name=(ir.parser or {}).get("name"),
        )

        chunks = chunk_parse_ir(ir, workspace_id=ws, settings=reg.settings)
        for c in chunks:
            c.object_key = meta.object_key
            c.source_file = meta.source_file
            c.url = ir.url

        reg.documents.update_status(meta.doc_id, "extracting")
        entities, relations = extract_from_chunks(chunks)

        reg.documents.update_status(meta.doc_id, "embedding")
        payloads = [c.to_payload() for c in chunks]
        # docs/knowledge/08: every point records its embedding model identity
        embed_model = active_embed_model(reg.settings)
        for p in payloads:
            p["embed_model"] = embed_model
        channels = {"vector": False, "bm25": False, "graph": False}
        warnings = list(ir.warnings)

        try:
            reg.vector.upsert_chunks(payloads)
            channels["vector"] = True
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"vector_upsert_failed:{exc}")
            logger.exception("vector upsert failed")

        try:
            for p in payloads:
                reg.bm25.upsert(p["chunk_id"], p.get("text", ""), p)
            channels["bm25"] = True
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"bm25_upsert_failed:{exc}")
            logger.exception("bm25 upsert failed")

        try:
            if hasattr(reg.graph, "upsert"):
                reg.graph.upsert(entities, relations)  # type: ignore[attr-defined]
            else:
                reg.graph.upsert_entities(entities)
                reg.graph.upsert_relations(relations)
            channels["graph"] = True
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"graph_upsert_failed:{exc}")
            logger.exception("graph upsert failed")

        for p in payloads:
            reg.chunk_payloads[p["chunk_id"]] = p

        status = "ready" if channels["vector"] and channels["bm25"] else "failed"
        if status == "ready" and not channels["graph"]:
            status = "ready_degraded"
        reg.documents.update_status(meta.doc_id, status)
        try:
            save_registry(reg)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"persist_failed:{exc}")

        return IngestResult(
            doc_id=meta.doc_id,
            status=status,
            chunk_count=len(chunks),
            entity_count=len(entities),
            relation_count=len(relations),
            object_key=meta.object_key,
            parser=(ir.parser or {}).get("name"),
            warnings=warnings,
            channels=channels,
        )

    def ingest_text(
        self,
        text: str,
        *,
        filename: str = "document.md",
        workspace_id: str | None = None,
        title: str | None = None,
        doc_id: str | None = None,
    ) -> IngestResult:
        return self.ingest_bytes(
            text.encode("utf-8"),
            filename=filename,
            mime_type="text/markdown",
            workspace_id=workspace_id,
            title=title,
            doc_id=doc_id,
        )

    def ingest_file(
        self,
        path: str | Path,
        *,
        workspace_id: str | None = None,
        title: str | None = None,
        doc_id: str | None = None,
    ) -> IngestResult:
        p = Path(path)
        data = p.read_bytes()
        return self.ingest_bytes(
            data,
            filename=p.name,
            workspace_id=workspace_id,
            title=title or p.stem,
            doc_id=doc_id,
        )

    def search(
        self,
        query: str,
        *,
        top_k: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        pack = self.registry.hybrid().retrieve(query, top_k=top_k, filters=filters)
        return pack.model_dump(mode="json")


def ingest_file(path: str | Path, **kwargs: Any) -> IngestResult:
    return KnowledgePipeline().ingest_file(path, **kwargs)


def ingest_text(text: str, **kwargs: Any) -> IngestResult:
    return KnowledgePipeline().ingest_text(text, **kwargs)


def search(query: str, **kwargs: Any) -> dict[str, Any]:
    return KnowledgePipeline().search(query, **kwargs)
