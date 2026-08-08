"""Research task endpoints (forward to Runtime or local echo)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status

from gateway.app.deps import PrincipalDep, RequestIdDep
from gateway.app.schemas.common import ApiResponse
from gateway.app.schemas.research import ResearchTask, ResearchTaskCreate, ResumeRequest
from gateway.app.services import chat_turns
from gateway.app.services import store as mem
from gateway.app.services.runtime_client import RuntimeClient

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
    """Create a task; server may route to PLC when query/path looks industrial."""
    runtime: RuntimeClient = request.app.state.runtime_client
    try:
        result = await chat_turns.handle_chat_turn(
            message=body.query,
            principal_subject=principal.subject,
            workspace_id=body.workspace_id or principal.workspace_id,
            session_id=body.session_id or principal.session_id,
            request_id=request_id,
            runtime=runtime,
            mode=body.mode,
            tia_export_dir=body.tia_export_dir,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "CHAT_INVALID", "message": str(exc)},
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PLC_PATH_NOT_FOUND", "message": str(exc)},
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "PLC_PATH_DENIED", "message": str(exc)},
        ) from exc

    return ApiResponse(
        ok=True,
        data=ResearchTask.model_validate(result["task"]),
        request_id=request_id,
    )


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
    if upstream and task.get("route") != "plc":
        task["status"] = upstream.get("status", task["status"])
        task["result"] = {**(task.get("result") or {}), "runtime": upstream}
        task["updated_at"] = datetime.now(timezone.utc)

    return ApiResponse(ok=True, data=ResearchTask.model_validate(task), request_id=request_id)


@router.delete("/tasks/{task_id}", response_model=ApiResponse[dict])
async def delete_task(
    task_id: str,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[dict]:
    """Delete a research/PLC conversation from the history list."""
    return _delete_task_impl(task_id, principal, request_id)


@router.post("/tasks/{task_id}/delete", response_model=ApiResponse[dict])
async def delete_task_post(
    task_id: str,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[dict]:
    """POST alias for environments that block HTTP DELETE."""
    return _delete_task_impl(task_id, principal, request_id)


def _delete_task_impl(
    task_id: str,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[dict]:
    _ = principal
    task = mem.store.tasks.pop(task_id, None)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND_TASK", "message": "Task not found"},
        )
    plc_job_id = task.get("plc_job_id") or (task.get("result") or {}).get("plc_job_id")
    plc_deleted = False
    if plc_job_id:
        from gateway.app.services import plc_jobs as plc

        plc_deleted = plc.delete_job(str(plc_job_id))
    return ApiResponse(
        ok=True,
        data={"deleted": task_id, "plc_job_deleted": plc_deleted},
        request_id=request_id,
    )


@router.get("/tasks/{task_id}/events")
async def task_events_stub(
    task_id: str,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[list[dict]]:
    _ = principal
    task = mem.store.tasks.get(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND_TASK", "message": "Task not found"},
        )
    return ApiResponse(ok=True, data=task.get("events") or [], request_id=request_id)


@router.post("/tasks/{task_id}/resume", response_model=ApiResponse[ResearchTask])
async def resume_task(
    task_id: str,
    body: ResumeRequest,
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
    upstream = await runtime.resume_task(task_id, body.model_dump())
    task["status"] = upstream.get("status", "running")
    task["result"] = {**(task.get("result") or {}), "runtime": upstream, "resume": body.model_dump()}
    task["interrupts"] = []
    task["updated_at"] = datetime.now(timezone.utc)
    return ApiResponse(ok=True, data=ResearchTask.model_validate(task), request_id=request_id)


@router.post("/tasks/{task_id}/cancel", response_model=ApiResponse[ResearchTask])
async def cancel_task(
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
    upstream = await runtime.cancel_task(task_id)
    task["status"] = upstream.get("status", "cancelled")
    task["result"] = {**(task.get("result") or {}), "runtime": upstream}
    task["updated_at"] = datetime.now(timezone.utc)
    return ApiResponse(ok=True, data=ResearchTask.model_validate(task), request_id=request_id)
