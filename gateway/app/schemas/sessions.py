"""Session schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    workspace_id: str | None = None
    title: str | None = Field(default=None, max_length=256)
    metadata: dict[str, str] | None = None


class SessionUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=256)
    metadata: dict[str, str] | None = None


class Session(BaseModel):
    id: str
    user_id: str
    workspace_id: str
    title: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
