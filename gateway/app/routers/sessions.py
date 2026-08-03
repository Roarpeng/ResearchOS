"""Session CRUD (in-memory Phase 1 stub)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from gateway.app.deps import PrincipalDep, RequestIdDep
from gateway.app.schemas.common import ApiResponse
from gateway.app.schemas.sessions import Session, SessionCreate, SessionUpdate
from gateway.app.services import store as mem
from gateway.app.services.store import new_session

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("", response_model=ApiResponse[Session], status_code=status.HTTP_201_CREATED)
async def create_session(
    body: SessionCreate,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[Session]:
    session = new_session(
        user_id=principal.subject,
        workspace_id=body.workspace_id or principal.workspace_id or "ws_dev",
        title=body.title,
        metadata=body.metadata,
    )
    return ApiResponse(ok=True, data=Session.model_validate(session), request_id=request_id)


@router.get("", response_model=ApiResponse[list[Session]])
async def list_sessions(
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[list[Session]]:
    items = [
        Session.model_validate(s)
        for s in mem.store.sessions.values()
        if s.get("user_id") == principal.subject
        or principal.auth_type in {"dev_anonymous", "api_key"}
    ]
    return ApiResponse(ok=True, data=items, request_id=request_id)


@router.get("/{session_id}", response_model=ApiResponse[Session])
async def get_session(
    session_id: str,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[Session]:
    session = mem.store.sessions.get(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND_SESSION", "message": "Session not found"},
        )
    return ApiResponse(ok=True, data=Session.model_validate(session), request_id=request_id)


@router.patch("/{session_id}", response_model=ApiResponse[Session])
async def update_session(
    session_id: str,
    body: SessionUpdate,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[Session]:
    session = mem.store.sessions.get(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND_SESSION", "message": "Session not found"},
        )
    if body.title is not None:
        session["title"] = body.title
    if body.metadata is not None:
        session["metadata"] = body.metadata
    session["updated_at"] = datetime.now(timezone.utc)
    return ApiResponse(ok=True, data=Session.model_validate(session), request_id=request_id)


@router.delete("/{session_id}", response_model=ApiResponse[dict])
async def delete_session(
    session_id: str,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[dict]:
    if session_id not in mem.store.sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND_SESSION", "message": "Session not found"},
        )
    mem.store.sessions.pop(session_id, None)
    return ApiResponse(ok=True, data={"deleted": session_id}, request_id=request_id)
