"""Unified conversation API — UI never chooses Research vs PLC."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile, status

from gateway.app.deps import PrincipalDep, RequestIdDep
from gateway.app.schemas.chat import ChatTurnResponse
from gateway.app.schemas.common import ApiResponse
from gateway.app.schemas.research import ResearchTask
from gateway.app.services import chat_turns
from gateway.app.services.runtime_client import RuntimeClient

logger = logging.getLogger("researchos.gateway.chat")

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post(
    "/turns",
    response_model=ApiResponse[ChatTurnResponse],
    status_code=status.HTTP_200_OK,
)
async def post_chat_turn(
    request: Request,
    principal: PrincipalDep,
    request_id: RequestIdDep,
    background: BackgroundTasks,
    message: str = Form(default=""),
    task_id: str | None = Form(default=None),
    mode: str = Form(default="deep"),
    tia_export_dir: str | None = Form(default=None),
    focus_node_id: str | None = Form(default=None),
    block_name: str | None = Form(default=None),
    canvas_edges: str | None = Form(default=None),
    canvas_positions: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
) -> ApiResponse[ChatTurnResponse]:
    runtime: RuntimeClient = request.app.state.runtime_client
    upload_bytes: bytes | None = None
    upload_name: str | None = None
    if file is not None and file.filename:
        upload_bytes = await file.read()
        upload_name = file.filename

    try:
        result = await chat_turns.handle_chat_turn(
            message=message,
            principal_subject=principal.subject,
            workspace_id=principal.workspace_id,
            session_id=principal.session_id,
            request_id=request_id,
            runtime=runtime,
            task_id=task_id or None,
            upload_bytes=upload_bytes,
            upload_filename=upload_name,
            mode=mode,
            tia_export_dir=tia_export_dir,
            focus_node_id=focus_node_id or None,
            block_name=block_name or None,
            canvas_edges_json=canvas_edges,
            canvas_positions_json=canvas_positions,
            background=background,
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
    except KeyError as exc:
        missing = str(exc).strip("'\"")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "SESSION_EXPIRED",
                "message": (
                    f"会话已失效（找不到 {missing}）。"
                    "Gateway 重启后内存中的任务/PLC 作业会清空，"
                    "请点「新建」并重新上传工程后再提问。"
                ),
            },
        ) from exc

    task = ResearchTask.model_validate(result["task"])
    plc_job_id = result["task"].get("plc_job_id") or (result["task"].get("result") or {}).get(
        "plc_job_id"
    )
    data = ChatTurnResponse(
        task=task,
        assistant_message=str(result["assistant_message"]),
        route=str(result["route"]),
        plc_job_id=str(plc_job_id) if plc_job_id else None,
        knowledge_canvas=result.get("knowledge_canvas"),
        citations=list(result.get("citations") or []),
    )
    logger.info(
        "chat turn ok route=%s task=%s plc=%s request_id=%s",
        data.route,
        task.id,
        data.plc_job_id,
        request_id,
    )
    return ApiResponse(ok=True, data=data, request_id=request_id)
