"""Normalized search hit schema for Search Router."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SearchHit(BaseModel):
    id: str
    title: str
    url: str | None = None
    source_id: str | None = None
    snippet: str = ""
    score: float = 0.0
    source_type: str = "web"
    published_at: str | None = None
    raw_provider: str = "mock"
    raw_ref: dict[str, Any] | None = None


class SearchQueryResult(BaseModel):
    ok: bool = True
    provider_used: str = "mock"
    results: list[SearchHit] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
