"""Research task endpoints (forward to Runtime or local echo)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status

from gateway.app.deps import PrincipalDep, RequestIdDep
from gateway.app.schemas.common import ApiResponse
from gateway.app.schemas.research import ResearchTask, ResearchTaskCreate, ResumeRequest
from gateway.app.services import store as mem
from gateway.app.services.runtime_client import RuntimeClient
from gateway.app.services.store import new_task

router = APIRouter(prefix="/api/v1/research", tags=["research"])


@router.post(
    "/tasks",
    response_model=ApiResponse[ResearchTask],
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    body: ResearchTaskCreate,
    request: Request,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[ResearchTask]:
    runtime: RuntimeClient = request.app.state.runtime_client
    payload = body.model_dump()
    payload["workspace_id"] = body.workspace_id or principal.workspace_id
    payload["session_id"] = body.session_id or principal.session_id
    payload["request_id"] = request_id
    payload["created_by"] = principal.subject

    task = new_task(
        {
            "query": body.query,
            "mode": body.mode,
            "workspace_id": payload["workspace_id"],
            "session_id": payload["session_id"],
            "options": body.options.model_dump(),
            "context": body.context.model_dump(),
        }
    )

    upstream = await runtime.create_task({**payload, "task_id": task["id"]})
    task["status"] = upstream.get("status", "queued")
    task["result"] = {"runtime": upstream}
    task["updated_at"] = datetime.now(timezone.utc)

    return ApiResponse(ok=True, data=ResearchTask.model_validate(task), request_id=request_id)


@router.get("/tasks", response_model=ApiResponse[list[ResearchTask]])
async def list_tasks(
    principal: PrincipalDep,
    request_id: RequestIdDep,
    workspace_id: str | None = None,
    limit: int = 20,
) -> ApiResponse[list[ResearchTask]]:
    items = list(mem.store.tasks.values())
    if workspace_id:
        items = [t for t in items if t.get("workspace_id") == workspace_id]
    items = sorted(items, key=lambda t: t["created_at"], reverse=True)[: max(1, min(limit, 100))]
    return ApiResponse(
        ok=True,
        data=[ResearchTask.model_validate(t) for t in items],
        request_id=request_id,
    )


@router.get("/tasks/{task_id}", response_model=ApiResponse[ResearchTask])
async def get_task(
    task_id: str,
    request: Request,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[ResearchTask]:
    task = mem.store.tasks.get(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND_TASK", "message": "Task not found"},
        )

    runtime: RuntimeClient = request.app.state.runtime_client
    upstream = await runtime.get_task(task_id)
    if upstream:
        task["status"] = upstream.get("status", task["status"])
        task["result"] = upstream
        task["updated_at"] = datetime.now(timezone.utc)

    return ApiResponse(ok=True, data=ResearchTask.model_validate(task), request_id=request_id)


@router.get("/tasks/{task_id}/events")
async def task_events_stub(task_id: str, principal: PrincipalDep) -> dict:
    """SSE placeholder — Phase 1 returns a static snapshot; prefer WebSocket."""
    task = mem.store.tasks.get(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND_TASK", "message": "Task not found"},
        )
    return {
        "ok": True,
        "data": {
            "task_id": task_id,
            "status": task.get("status"),
            "message": "stub: use WebSocket /api/v1/ws/research/{task_id} for streaming",
        },
    }


@router.post("/tasks/{task_id}/resume", response_model=ApiResponse[ResearchTask])
async def resume_task(
    task_id: str,
    body: ResumeRequest,
    request: Request,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[ResearchTask]:
    """Resume a task waiting for human approval (HITL)."""
    task = mem.store.tasks.get(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND_TASK", "message": "Task not found"},
        )

    runtime: RuntimeClient = request.app.state.runtime_client
    upstream = await runtime.resume_task(
        task_id,
        resolution=body.resolution,
        interrupt_id=body.interrupt_id,
    )
    if upstream:
        task["status"] = upstream.get("status", task["status"])
        task["result"] = upstream
        task["updated_at"] = datetime.now(timezone.utc)

    return ApiResponse(
        ok=True,
        data=ResearchTask.model_validate(task),
        request_id=request_id,
    )


@router.post("/tasks/{task_id}/cancel", response_model=ApiResponse[ResearchTask])
async def cancel_task(
    task_id: str,
    request: Request,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[ResearchTask]:
    """Cancel a running or waiting research task."""
    task = mem.store.tasks.get(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND_TASK", "message": "Task not found"},
        )

    runtime: RuntimeClient = request.app.state.runtime_client
    upstream = await runtime.cancel_task(task_id)
    task["status"] = "cancelled"
    task["updated_at"] = datetime.now(timezone.utc)
    if upstream:
        task["result"] = upstream

    return ApiResponse(
        ok=True,
        data=ResearchTask.model_validate(task),
        request_id=request_id,
    )
