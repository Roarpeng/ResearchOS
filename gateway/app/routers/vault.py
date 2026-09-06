"""Vault router — research-folder scan/ingest into the knowledge layer."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from gateway.app.deps import PrincipalDep, RequestIdDep
from gateway.app.schemas.common import ApiResponse

logger = logging.getLogger("researchos.gateway.vault")

router = APIRouter(prefix="/api/v1/vault", tags=["vault"])


class VaultScanRequest(BaseModel):
    root: str


class VaultIngestRequest(BaseModel):
    root: str
    workspace_id: str | None = None


class VaultIngestResponse(BaseModel):
    scanned: int = 0
    ingested: int = 0
    skipped_unchanged: int = 0
    skipped_unsupported: int = 0
    failed: int = 0
    details: list[dict] = Field(default_factory=list)


@router.post("/scan", response_model=ApiResponse[dict])
async def scan_vault(
    body: VaultScanRequest,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[dict]:
    _ = principal
    from tools.vault import core

    entries = core.scan(body.root)
    return ApiResponse(
        ok=True,
        data={
            "count": len(entries),
            "supported": sum(1 for e in entries if e.supported),
            "files": [
                {"path": e.path, "size": e.size, "supported": e.supported} for e in entries
            ],
        },
        request_id=request_id,
    )


@router.post("/ingest", response_model=ApiResponse[VaultIngestResponse])
async def ingest_vault(
    body: VaultIngestRequest,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[VaultIngestResponse]:
    _ = principal
    from tools.vault import core

    # Folder ingest is CPU/IO-bound; run off the event loop.
    result = await asyncio.to_thread(core.ingest, body.root, body.workspace_id)
    return ApiResponse(
        ok=True,
        data=VaultIngestResponse(
            scanned=result.scanned,
            ingested=result.ingested,
            skipped_unchanged=result.skipped_unchanged,
            skipped_unsupported=result.skipped_unsupported,
            failed=result.failed,
            details=result.details,
        ),
        request_id=request_id,
    )
