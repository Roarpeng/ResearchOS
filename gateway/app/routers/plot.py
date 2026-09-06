"""Plot router — data file → reproducible code → PNG (via tools.plot)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from gateway.app.deps import PrincipalDep, RequestIdDep
from gateway.app.schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1/plot", tags=["plot"])


class PlotColumnsRequest(BaseModel):
    path: str


class PlotRenderRequest(BaseModel):
    path: str
    x: str
    y: str
    kind: str = "bar"
    title: str = ""
    out_dir: str | None = None


@router.post("/columns", response_model=ApiResponse[dict])
async def plot_columns(
    body: PlotColumnsRequest,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[dict]:
    _ = principal
    from tools.plot import core

    return ApiResponse(ok=True, data=core.read_columns(body.path), request_id=request_id)


@router.post("/render", response_model=ApiResponse[dict])
async def plot_render(
    body: PlotRenderRequest,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[dict]:
    _ = principal
    from tools.plot import core

    result = await asyncio.to_thread(
        core.render,
        body.path,
        body.x,
        body.y,
        kind=body.kind,
        title=body.title,
        out_dir=body.out_dir,
    )
    return ApiResponse(ok=True, data=result, request_id=request_id)
