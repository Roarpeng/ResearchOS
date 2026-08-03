"""Knowledge upload/search stubs."""

from __future__ import annotations

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
    space["document_count"] = int(space.get("document_count", 0)) + 1
    await file.read(1024)  # drain a bit; full ingest arrives in Phase 3
    return ApiResponse(
        ok=True,
        data=DocumentUploadResponse(
            id=doc_id,
            knowledge_space_id=kb_id,
            title=title or file.filename,
            status="queued",
            message="stub: ingestion not yet wired",
        ),
        request_id=request_id,
    )


@router.post("/search", response_model=ApiResponse[SearchResponse])
async def search(
    body: SearchRequest,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[SearchResponse]:
    placeholder = SearchHit(
        citation_id=f"cit_{uuid4().hex[:10]}",
        score=0.0,
        text="stub hit — wire Hybrid GraphRAG in Phase 3",
        source_id="src_stub",
        locator=None,
        metadata={"query": body.query, "mode": body.mode},
    )
    return ApiResponse(
        ok=True,
        data=SearchResponse(query=body.query, hits=[placeholder]),
        request_id=request_id,
    )
