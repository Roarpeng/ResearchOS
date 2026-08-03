"""Knowledge API schemas (Phase 1 stubs)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class KnowledgeSpaceCreate(BaseModel):
    workspace_id: str | None = None
    name: str = Field(min_length=1, max_length=256)
    description: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSpace(BaseModel):
    id: str
    name: str
    description: str | None = None
    status: str = "ready"
    document_count: int = 0
    workspace_id: str | None = None
    created_at: datetime


class DocumentUploadResponse(BaseModel):
    id: str
    knowledge_space_id: str
    title: str | None = None
    status: str = "queued"
    message: str = "stub: ingestion not yet wired"


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    knowledge_space_ids: list[str] = Field(default_factory=list)
    top_k: int = Field(default=8, ge=1, le=50)
    mode: str = "hybrid"


class SearchHit(BaseModel):
    citation_id: str
    score: float
    text: str
    source_id: str
    locator: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]
    message: str = "stub: retrieval not yet wired"
