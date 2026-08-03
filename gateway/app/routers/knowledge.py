"""Knowledge upload/search — wired to KnowledgePipeline."""

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

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
from gateway.app.services import store as mem
from gateway.app.services.store import new_space

logger = logging.getLogger("researchos.gateway.knowledge")

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


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
    items = [KnowledgeSpace.model_validate(s) for s in mem.store.spaces.values()]
    return ApiResponse(ok=True, data=items, request_id=request_id)


@router.get("/spaces/{kb_id}", response_model=ApiResponse[KnowledgeSpace])
async def get_space(
    kb_id: str,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[KnowledgeSpace]:
    space = mem.store.spaces.get(kb_id)
    if not space:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND_SPACE", "message": "Knowledge space not found"},
        )
    return ApiResponse(ok=True, data=KnowledgeSpace.model_validate(space), request_id=request_id)


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

    # Wire to real KnowledgePipeline (graceful fallback if unavailable)
    chunk_count = 0
    entity_count = 0
    channels: dict[str, bool] = {}
    warnings: list[str] = []
    ingest_status = "queued"
    try:
        from knowledge.pipeline import KnowledgePipeline

        pipeline = KnowledgePipeline()
        result = pipeline.ingest_bytes(
            data,
            filename=file.filename,
            mime_type=file.content_type,
            workspace_id=space.get("workspace_id"),
            title=title or file.filename,
            doc_id=doc_id,
        )
        chunk_count = result.chunk_count
        entity_count = result.entity_count
        channels = result.channels
        warnings = result.warnings
        ingest_status = result.status
        logger.info(
            "ingested doc_id=%s chunks=%d entities=%d status=%s",
            doc_id, chunk_count, entity_count, ingest_status,
        )
    except ImportError:
        warnings.append("knowledge_pipeline_not_available")
        logger.warning("knowledge pipeline not importable; returning stub")
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"ingest_failed:{exc}")
        logger.exception("document ingest failed")
        ingest_status = "failed"

    space["document_count"] = int(space.get("document_count", 0)) + 1
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
    hits: list[SearchHit] = []
    passages: list[dict] = []
    diagnostics: dict = {}
    message = ""

    try:
        from knowledge.pipeline import KnowledgePipeline

        pipeline = KnowledgePipeline()
        pack = pipeline.search(body.query, top_k=body.top_k)
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
                    locator=cit.get("locator"),
                    metadata={
                        "channels": p.get("channels", []),
                        "chunk_id": p.get("chunk_id", ""),
                    },
                )
            )
        message = f"retrieved {len(hits)} passages via hybrid RRF"
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
            passages=passages[:body.top_k],
            diagnostics=diagnostics,
            message=message,
        ),
        request_id=request_id,
    )
