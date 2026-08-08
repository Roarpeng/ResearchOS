"""Agent tools / MCP / skill settings schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentToolItem(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    enabled: bool = True
    command: str = ""


class McpServerItem(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    enabled: bool = True
    transport: str = "stdio"
    command: str = ""
    url: str = ""
    args: str = ""
    source: str = ""
    hub_name: str = ""


class SkillItem(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    enabled: bool = True
    path: str = ""
    source: str = "local"
    hub_id: str = ""


class AgentWorkspaceSettings(BaseModel):
    tools: list[AgentToolItem] = Field(default_factory=list)
    mcp_servers: list[McpServerItem] = Field(default_factory=list)
    skills: list[SkillItem] = Field(default_factory=list)


class AgentWorkspaceUpdate(BaseModel):
    tools: list[AgentToolItem] | None = None
    mcp_servers: list[McpServerItem] | None = None
    skills: list[SkillItem] | None = None
