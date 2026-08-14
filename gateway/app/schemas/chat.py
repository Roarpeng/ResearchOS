"""Unified chat turn schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from gateway.app.schemas.research import ResearchTask


class ChatTurnResponse(BaseModel):
    task: ResearchTask
    assistant_message: str
    route: str = Field(description="research | plc")
    plc_job_id: str | None = None
    knowledge_canvas: dict | None = None
    citations: list[dict] = Field(default_factory=list)
