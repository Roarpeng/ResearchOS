"""LLM / agent model settings API + public hub install."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from gateway.app.deps import PrincipalDep, RequestIdDep
from gateway.app.schemas.agent_workspace import AgentWorkspaceSettings, AgentWorkspaceUpdate
from gateway.app.schemas.common import ApiResponse
from gateway.app.schemas.llm import LlmSettingsResponse, LlmSettingsUpdate
from gateway.app.services import agent_workspace_settings as aws
from gateway.app.services import hub_catalog as hub
from gateway.app.services import llm_settings as svc

logger = logging.getLogger("researchos.gateway.settings")

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class HubInstallMcpRequest(BaseModel):
    item: dict[str, Any]


class HubInstallSkillRequest(BaseModel):
    item: dict[str, Any]


@router.get("/llm", response_model=ApiResponse[LlmSettingsResponse])
async def get_llm_settings(
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[LlmSettingsResponse]:
    _ = principal
    return ApiResponse(ok=True, data=svc.get_llm_settings(), request_id=request_id)


@router.put("/llm", response_model=ApiResponse[LlmSettingsResponse])
async def put_llm_settings(
    body: LlmSettingsUpdate,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[LlmSettingsResponse]:
    _ = principal
    try:
        data = svc.update_llm_settings(body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "LLM_SETTINGS_INVALID", "message": str(exc)},
        ) from exc
    logger.info("llm settings updated by=%s", principal.subject)
    return ApiResponse(ok=True, data=data, request_id=request_id)


@router.get("/agent-workspace", response_model=ApiResponse[AgentWorkspaceSettings])
async def get_agent_workspace(
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[AgentWorkspaceSettings]:
    _ = principal
    data = aws.get_agent_workspace_settings()
    return ApiResponse(
        ok=True,
        data=AgentWorkspaceSettings.model_validate(data),
        request_id=request_id,
    )


@router.put("/agent-workspace", response_model=ApiResponse[AgentWorkspaceSettings])
async def put_agent_workspace(
    body: AgentWorkspaceUpdate,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[AgentWorkspaceSettings]:
    _ = principal
    try:
        data = aws.update_agent_workspace_settings(body.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "AGENT_WORKSPACE_INVALID", "message": str(exc)},
        ) from exc
    logger.info("agent workspace settings updated by=%s", principal.subject)
    return ApiResponse(
        ok=True,
        data=AgentWorkspaceSettings.model_validate(data),
        request_id=request_id,
    )


@router.get("/hub/mcp")
async def search_mcp_hub(
    principal: PrincipalDep,
    request_id: RequestIdDep,
    query: str = "",
    limit: int = 20,
) -> ApiResponse[dict]:
    _ = principal
    limit = max(1, min(int(limit or 20), 50))
    data = hub.search_mcp_hub(query, limit=limit)
    return ApiResponse(ok=True, data=data, request_id=request_id)


@router.get("/hub/skills")
async def search_skills_hub(
    principal: PrincipalDep,
    request_id: RequestIdDep,
    query: str = "",
    limit: int = 20,
) -> ApiResponse[dict]:
    _ = principal
    limit = max(1, min(int(limit or 20), 50))
    data = hub.search_skills_hub(query, limit=limit)
    return ApiResponse(ok=True, data=data, request_id=request_id)


@router.post("/hub/mcp/install", response_model=ApiResponse[AgentWorkspaceSettings])
async def install_mcp_hub(
    body: HubInstallMcpRequest,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[AgentWorkspaceSettings]:
    _ = principal
    try:
        installed = hub.install_mcp_from_hub(body.item)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "HUB_INSTALL_INVALID", "message": str(exc)},
        ) from exc
    current = aws.get_agent_workspace_settings()
    mcp = list(current.get("mcp_servers") or [])
    key = installed.get("hub_name") or installed.get("name")
    mcp = [m for m in mcp if (m.get("hub_name") or m.get("name")) != key]
    mcp.insert(0, installed)
    data = aws.update_agent_workspace_settings({"mcp_servers": mcp})
    logger.info("mcp hub install by=%s name=%s", principal.subject, installed.get("name"))
    return ApiResponse(
        ok=True,
        data=AgentWorkspaceSettings.model_validate(data),
        request_id=request_id,
    )


@router.post("/hub/skills/install", response_model=ApiResponse[AgentWorkspaceSettings])
async def install_skill_hub(
    body: HubInstallSkillRequest,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[AgentWorkspaceSettings]:
    _ = principal
    skills_root = Path.cwd() / ".agents" / "skills"
    try:
        installed = hub.install_skill_from_hub(body.item, skills_root=skills_root)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "HUB_INSTALL_INVALID", "message": str(exc)},
        ) from exc
    current = aws.get_agent_workspace_settings()
    skills = list(current.get("skills") or [])
    skills = [s for s in skills if s.get("name") != installed.get("name")]
    skills.insert(0, installed)
    data = aws.update_agent_workspace_settings({"skills": skills})
    logger.info("skill hub install by=%s name=%s", principal.subject, installed.get("name"))
    return ApiResponse(
        ok=True,
        data=AgentWorkspaceSettings.model_validate(data),
        request_id=request_id,
    )
