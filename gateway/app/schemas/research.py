"""Research task schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ResearchOptions(BaseModel):
    language: str = "zh-CN"
    max_steps: int = 24
    enable_web: bool = True
    enable_knowledge: bool = True
    citation_required: bool = True
    report_format: list[str] = Field(default_factory=lambda: ["markdown"])
    model_profile: str = "default"
    human_interrupt: Literal["never", "on_review", "always_plan"] = "on_review"


class ResearchContext(BaseModel):
    knowledge_space_ids: list[str] = Field(default_factory=list)
    seed_urls: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class ResearchTaskCreate(BaseModel):
    query: str = Field(min_length=1, max_length=8000)
    workspace_id: str | None = None
    session_id: str | None = None
    mode: Literal["quick", "deep", "industrial"] = "deep"
    tia_export_dir: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional TIA Openness export directory for PLC agent analysis",
    )
    options: ResearchOptions = Field(default_factory=ResearchOptions)
    context: ResearchContext = Field(default_factory=ResearchContext)


class StreamLinks(BaseModel):
    ws_url: str
    sse_url: str


class ResearchTask(BaseModel):
    id: str
    status: str
    query: str
    mode: str
    workspace_id: str | None = None
    session_id: str | None = None
    created_at: datetime
    updated_at: datetime
    stream: StreamLinks | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    plan: Any = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    interrupts: list[dict[str, Any]] = Field(default_factory=list)


class ResumeRequest(BaseModel):
    resolution: str | dict[str, Any] = "approve"
    interrupt_id: str | None = None
