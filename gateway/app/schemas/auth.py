"""Auth request/response schemas (Phase 1 stubs)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str
    workspace_id: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None
    all_sessions: bool = False


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800
    session: dict[str, str] | None = None


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(default="dev-key", max_length=128)
    scopes: list[str] = Field(default_factory=lambda: ["research:write", "knowledge:read"])


class ApiKeyCreateResponse(BaseModel):
    id: str
    name: str
    api_key: str
    scopes: list[str]


class MeResponse(BaseModel):
    id: str
    email: str | None = None
    workspace_id: str | None = None
    scopes: list[str] = Field(default_factory=list)
    auth_type: str
