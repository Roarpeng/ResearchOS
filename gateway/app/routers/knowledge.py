"""Knowledge upload/search/graph — wired to KnowledgePipeline + knowledge_service."""

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from gateway.app.deps import PrincipalDep, RequestIdDep
from gateway.app.schemas.common import ApiResponse
from gateway.app.schemas.knowledge import (
    DocumentUploadResponse,
    KnowledgeSpace,
    KnowledgeSpaceCreate,
    SearchHit,
    SearchRequest,
    SearchResponse,
)
from gateway.app.services import knowledge_service as ksvc
from gateway.app.services import store as mem
from gateway.app.services.store import new_space

logger = logging.getLogger("researchos.gateway.knowledge")

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


class KnowledgeStats(BaseModel):
    space_id: str | None = None
    document_count: int = 0
    chunk_count: int = 0
    entity_count: int = 0
    relation_count: int = 0
    documents: list[dict] = Field(default_factory=list)
    channels: dict[str, bool] = Field(default_factory=dict)


class RebuildResponse(BaseModel):
    ok: bool = True
    chunk_count: int = 0
    channels: dict[str, bool] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    space_id: str | None = None


@router.post(
    "/spaces",
    response_model=ApiResponse[KnowledgeSpace],
    status_code=status.HTTP_201_CREATED,
)
async def create_space(
    body: KnowledgeSpaceCreate,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[KnowledgeSpace]:
    space = new_space(
        name=body.name,
        workspace_id=body.workspace_id or principal.workspace_id,
        description=body.description,
        settings=body.settings,
    )
    return ApiResponse(ok=True, data=KnowledgeSpace.model_validate(space), request_id=request_id)


@router.get("/spaces", response_model=ApiResponse[list[KnowledgeSpace]])
async def list_spaces(
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[list[KnowledgeSpace]]:
    _ = principal
    items = [KnowledgeSpace.model_validate(s) for s in mem.store.spaces.values()]
    return ApiResponse(ok=True, data=items, request_id=request_id)


@router.get("/spaces/{kb_id}", response_model=ApiResponse[KnowledgeSpace])
async def get_space(
    kb_id: str,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[KnowledgeSpace]:
    _ = principal
    space = mem.store.spaces.get(kb_id)
    if not space:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND_SPACE", "message": "Knowledge space not found"},
        )
    return ApiResponse(ok=True, data=KnowledgeSpace.model_validate(space), request_id=request_id)


@router.get("/spaces/{kb_id}/stats", response_model=ApiResponse[KnowledgeStats])
async def space_stats(
    kb_id: str,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[KnowledgeStats]:
    _ = principal
    if kb_id not in mem.store.spaces:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND_SPACE", "message": "Knowledge space not found"},
        )
    return ApiResponse(
        ok=True,
        data=KnowledgeStats.model_validate(ksvc.space_stats(kb_id)),
        request_id=request_id,
    )


class ChunkListResponse(BaseModel):
    space_id: str | None = None
    doc_id: str | None = None
    count: int = 0
    chunks: list[dict] = Field(default_factory=list)


@router.get("/spaces/{kb_id}/chunks", response_model=ApiResponse[ChunkListResponse])
async def space_chunks(
    kb_id: str,
    principal: PrincipalDep,
    request_id: RequestIdDep,
    doc_id: str | None = None,
    limit: int = 80,
) -> ApiResponse[ChunkListResponse]:
    _ = principal
    if kb_id not in mem.store.spaces:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND_SPACE", "message": "Knowledge space not found"},
        )
    data = ksvc.list_chunks(kb_id, doc_id=doc_id or None, limit=limit)
    return ApiResponse(ok=True, data=ChunkListResponse.model_validate(data), request_id=request_id)


@router.get("/spaces/{kb_id}/graph", response_model=ApiResponse[dict])
async def space_graph(
    kb_id: str,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[dict]:
    _ = principal
    if kb_id not in mem.store.spaces:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND_SPACE", "message": "Knowledge space not found"},
        )
    return ApiResponse(ok=True, data=ksvc.graph_snapshot(kb_id), request_id=request_id)


@router.post("/spaces/{kb_id}/rebuild", response_model=ApiResponse[RebuildResponse])
async def rebuild_space(
    kb_id: str,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[RebuildResponse]:
    _ = principal
    if kb_id not in mem.store.spaces:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND_SPACE", "message": "Knowledge space not found"},
        )
    result = ksvc.rebuild_indexes(space_id=kb_id)
    return ApiResponse(ok=True, data=RebuildResponse.model_validate(result), request_id=request_id)


@router.post(
    "/spaces/{kb_id}/documents",
    response_model=ApiResponse[DocumentUploadResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    kb_id: str,
    principal: PrincipalDep,
    request_id: RequestIdDep,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
) -> ApiResponse[DocumentUploadResponse]:
    if kb_id not in mem.store.spaces:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND_SPACE", "message": "Knowledge space not found"},
        )
    doc_id = f"doc_{uuid4().hex[:16]}"
    space = mem.store.spaces[kb_id]

    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EMPTY_FILE", "message": "Uploaded file is empty"},
        )

    chunk_count = 0
    entity_count = 0
    channels: dict[str, bool] = {}
    warnings: list[str] = []
    ingest_status = "queued"
    try:
        result = ksvc.ingest_document(
            space_id=kb_id,
            data=data,
            filename=file.filename,
            mime_type=file.content_type,
            title=title or file.filename,
            doc_id=doc_id,
        )
        chunk_count = int(result.get("chunk_count") or 0)
        entity_count = int(result.get("entity_count") or 0)
        channels = dict(result.get("channels") or {})
        warnings = list(result.get("warnings") or [])
        ingest_status = str(result.get("status") or "ready")
        logger.info(
            "ingested doc_id=%s chunks=%d entities=%d status=%s",
            doc_id,
            chunk_count,
            entity_count,
            ingest_status,
        )
    except ImportError:
        warnings.append("knowledge_pipeline_not_available")
        logger.warning("knowledge pipeline not importable; returning stub")
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"ingest_failed:{exc}")
        logger.exception("document ingest failed")
        ingest_status = "failed"

    from datetime import datetime, timezone

    space["document_count"] = int(space.get("document_count", 0)) + 1
    docs = space.setdefault("documents", [])
    if isinstance(docs, list):
        docs.insert(
            0,
            {
                "id": doc_id,
                "title": title or file.filename,
                "filename": file.filename,
                "status": ingest_status,
                "chunk_count": chunk_count,
                "entity_count": entity_count,
                "channels": channels,
                "created_at": datetime.now(timezone.utc),
            },
        )
    return ApiResponse(
        ok=True,
        data=DocumentUploadResponse(
            id=doc_id,
            knowledge_space_id=kb_id,
            title=title or file.filename,
            status=ingest_status,
            message="ingested" if ingest_status != "failed" else "ingestion failed",
            chunk_count=chunk_count,
            entity_count=entity_count,
            channels=channels,
            warnings=warnings,
        ),
        request_id=request_id,
    )


@router.post("/search", response_model=ApiResponse[SearchResponse])
async def search(
    body: SearchRequest,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[SearchResponse]:
    _ = principal
    hits: list[SearchHit] = []
    passages: list[dict] = []
    diagnostics: dict = {}
    message = ""

    try:
        pack = ksvc.recall(
            body.query,
            knowledge_space_ids=body.knowledge_space_ids or None,
            top_k=body.top_k,
            mode=body.mode or "hybrid",
        )
        passages = pack.get("passages") or []
        diagnostics = pack.get("diagnostics") or {}
        for p in passages:
            cit = p.get("citation") or {}
            hits.append(
                SearchHit(
                    citation_id=cit.get("source_id") or p.get("chunk_id", ""),
                    score=float(p.get("score", 0.0)),
                    text=p.get("text", "")[:500],
                    source_id=cit.get("source_id") or p.get("source_id", ""),
                    locator=(cit.get("locator") or {}).get("url")
                    if isinstance(cit.get("locator"), dict)
                    else cit.get("locator"),
                    metadata={
                        "channels": p.get("channels", []),
                        "chunk_id": p.get("chunk_id", ""),
                    },
                )
            )
        message = (
            f"retrieved {len(hits)} passages via vector"
            if (pack.get("mode") or body.mode) == "vector"
            else f"retrieved {len(hits)} passages via hybrid RRF"
        )
        logger.info("search query=%r hits=%d", body.query[:80], len(hits))
    except ImportError:
        message = "knowledge_pipeline_not_available"
        logger.warning("knowledge pipeline not importable for search")
    except Exception as exc:  # noqa: BLE001
        message = f"search_failed:{exc}"
        logger.exception("hybrid search failed")

    return ApiResponse(
        ok=True,
        data=SearchResponse(
            query=body.query,
            hits=hits,
            passages=passages[: body.top_k],
            diagnostics=diagnostics,
            message=message,
        ),
        request_id=request_id,
    )
