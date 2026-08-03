"""Liveness and readiness probes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Response, status

from gateway.app.config import get_settings
from gateway.app.schemas.health import LiveResponse, ReadyResponse

logger = logging.getLogger("researchos.gateway.health")

router = APIRouter(prefix="/api/v1/health", tags=["health"])


async def _check_postgres(database_url: str | None) -> str:
    if not database_url:
        return "skipped"
    try:
        import asyncpg

        # Strip SQLAlchemy driver prefix if present
        dsn = database_url.replace("postgresql+asyncpg://", "postgresql://")
        conn = await asyncpg.connect(dsn=dsn, timeout=3)
        try:
            await conn.execute("SELECT 1")
        finally:
            await conn.close()
        return "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("postgres check failed: %s", exc)
        return "fail"


async def _check_redis(redis_url: str | None) -> str:
    if not redis_url:
        return "skipped"
    try:
        from redis.asyncio import Redis

        client = Redis.from_url(redis_url, socket_connect_timeout=2)
        try:
            pong = await client.ping()
            return "ok" if pong else "fail"
        finally:
            await client.aclose()
    except Exception as exc:  # noqa: BLE001
        logger.warning("redis check failed: %s", exc)
        return "fail"


@router.get("/live", response_model=LiveResponse)
async def live() -> LiveResponse:
    return LiveResponse(status="ok")


@router.get("/ready", response_model=ReadyResponse)
async def ready(response: Response) -> ReadyResponse:
    settings = get_settings()
    checks: dict[str, str] = {
        "postgres": await _check_postgres(settings.database_url),
        "redis": await _check_redis(settings.redis_url),
    }

    # Optional signals (informational)
    checks["litellm"] = "configured" if settings.litellm_base_url else "skipped"
    checks["runtime"] = "configured" if settings.runtime_base_url else "skipped"

    required_failed = any(
        checks[name] == "fail" for name in ("postgres", "redis") if checks[name] != "skipped"
    )
    any_probed = any(checks[n] != "skipped" for n in ("postgres", "redis"))

    if required_failed:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadyResponse(status="not_ready", checks=checks)

    # Dev / local: if URLs unset, report degraded but OK (200)
    if not any_probed and settings.is_dev:
        return ReadyResponse(status="degraded", checks=checks)

    if not any_probed:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadyResponse(status="not_ready", checks=checks)

    return ReadyResponse(status="ready", checks=checks)


@router.get("", include_in_schema=False)
@router.get("/", include_in_schema=False)
async def health_alias() -> dict[str, str]:
    """Convenience alias used by some smoke scripts."""
    return {"status": "ok"}
