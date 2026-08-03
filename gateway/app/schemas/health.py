"""Health check response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LiveResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadyResponse(BaseModel):
    status: Literal["ready", "degraded", "not_ready"]
    checks: dict[str, str] = Field(default_factory=dict)
