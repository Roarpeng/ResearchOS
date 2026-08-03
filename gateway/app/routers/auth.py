"""Auth stubs: JWT / API key issue and validate (dev-friendly)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import APIRouter, HTTPException, status

from gateway.app.deps import PrincipalDep, RequestIdDep, SettingsDep
from gateway.app.schemas.auth import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    LoginRequest,
    LogoutRequest,
    MeResponse,
    RefreshRequest,
    TokenPair,
)
from gateway.app.schemas.common import ApiResponse
from gateway.app.services import store as mem
from gateway.app.services.store import new_session

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _issue_tokens(
    *,
    settings: SettingsDep,
    user_id: str,
    workspace_id: str,
    session_id: str,
) -> TokenPair:
    now = datetime.now(timezone.utc)
    access_payload = {
        "sub": user_id,
        "sid": session_id,
        "wid": workspace_id,
        "scopes": ["research:write", "knowledge:write", "knowledge:read"],
        "typ": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.jwt_ttl_seconds)).timestamp()),
        "jti": f"jti_{uuid4().hex}",
    }
    access = jwt.encode(access_payload, settings.jwt_secret, algorithm="HS256")
    refresh = f"rt_{uuid4().hex}"
    mem.store.refresh_tokens[refresh] = {
        "user_id": user_id,
        "session_id": session_id,
        "workspace_id": workspace_id,
        "expires_at": now + timedelta(seconds=settings.refresh_ttl_seconds),
    }
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.jwt_ttl_seconds,
        session={
            "id": session_id,
            "workspace_id": workspace_id,
            "user_id": user_id,
        },
    )


@router.post("/login", response_model=ApiResponse[TokenPair])
async def login(
    body: LoginRequest,
    settings: SettingsDep,
    request_id: RequestIdDep,
) -> ApiResponse[TokenPair]:
    # Phase 1 stub: accept any non-empty password in dev
    if not body.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_INVALID_CREDENTIALS", "message": "Invalid credentials"},
        )
    user_id = f"usr_{uuid4().hex[:12]}"
    workspace_id = body.workspace_id or "ws_dev"
    session = new_session(user_id=user_id, workspace_id=workspace_id, title="login")
    tokens = _issue_tokens(
        settings=settings,
        user_id=user_id,
        workspace_id=workspace_id,
        session_id=session["id"],
    )
    return ApiResponse(ok=True, data=tokens, request_id=request_id)


@router.post("/refresh", response_model=ApiResponse[TokenPair])
async def refresh(
    body: RefreshRequest,
    settings: SettingsDep,
    request_id: RequestIdDep,
) -> ApiResponse[TokenPair]:
    record = mem.store.refresh_tokens.get(body.refresh_token)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_INVALID_TOKEN", "message": "Invalid refresh token"},
        )
    # rotate
    mem.store.refresh_tokens.pop(body.refresh_token, None)
    tokens = _issue_tokens(
        settings=settings,
        user_id=record["user_id"],
        workspace_id=record["workspace_id"],
        session_id=record["session_id"],
    )
    return ApiResponse(ok=True, data=tokens, request_id=request_id)


@router.post("/logout", response_model=ApiResponse[dict])
async def logout(
    body: LogoutRequest,
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[dict]:
    if body.refresh_token:
        mem.store.refresh_tokens.pop(body.refresh_token, None)
    if body.all_sessions:
        to_drop = [
            k
            for k, v in mem.store.refresh_tokens.items()
            if v.get("user_id") == principal.subject
        ]
        for k in to_drop:
            mem.store.refresh_tokens.pop(k, None)
    return ApiResponse(ok=True, data={"logged_out": True}, request_id=request_id)


@router.get("/me", response_model=ApiResponse[MeResponse])
async def me(principal: PrincipalDep, request_id: RequestIdDep) -> ApiResponse[MeResponse]:
    return ApiResponse(
        ok=True,
        data=MeResponse(
            id=principal.subject,
            email=None,
            workspace_id=principal.workspace_id,
            scopes=principal.scopes,
            auth_type=principal.auth_type,
        ),
        request_id=request_id,
    )


@router.post("/api-keys", response_model=ApiResponse[ApiKeyCreateResponse])
async def create_api_key(
    body: ApiKeyCreateRequest,
    principal: PrincipalDep,
    settings: SettingsDep,
    request_id: RequestIdDep,
) -> ApiResponse[ApiKeyCreateResponse]:
    if not settings.auth_api_keys_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "PERM_API_KEYS_DISABLED", "message": "API keys disabled"},
        )
    key_id = f"ak_{uuid4().hex[:12]}"
    plaintext = f"ros_ak_{uuid4().hex}"
    mem.store.api_keys[key_id] = {
        "id": key_id,
        "name": body.name,
        "owner": principal.subject,
        "scopes": body.scopes,
        "prefix": plaintext[:16],
    }
    return ApiResponse(
        ok=True,
        data=ApiKeyCreateResponse(
            id=key_id,
            name=body.name,
            api_key=plaintext,
            scopes=body.scopes,
        ),
        request_id=request_id,
    )


@router.post("/validate", response_model=ApiResponse[MeResponse])
async def validate_credentials(
    principal: PrincipalDep,
    request_id: RequestIdDep,
) -> ApiResponse[MeResponse]:
    """Validate current Authorization / X-API-Key credentials."""
    return await me(principal, request_id)
