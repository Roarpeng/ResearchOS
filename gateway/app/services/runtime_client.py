"""HTTP client for LangGraph Runtime (Phase 1 stub-friendly)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("researchos.gateway.runtime_client")


class RuntimeClient:
    def __init__(self, base_url: str | None, timeout: float = 30.0) -> None:
        self.base_url = (base_url or "").rstrip("/") or None
        self._client: httpx.AsyncClient | None = None
        self._timeout = timeout

    async def startup(self) -> None:
        if self.base_url:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self._timeout)

    async def shutdown(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def configured(self) -> bool:
        return self.base_url is not None

    async def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST task to Runtime if configured; otherwise local echo stub."""
        if not self._client or not self.base_url:
            return {
                "status": "queued",
                "runtime": "local_echo",
                "echo": payload,
            }
        try:
            resp = await self._client.post("/api/v1/runs", json=payload)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001 — Phase 1 soft-fail to local echo
            logger.warning("runtime create_task failed, falling back to echo: %s", exc)
            return {
                "status": "queued",
                "runtime": "local_echo_fallback",
                "echo": payload,
                "upstream_error": str(exc),
            }

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        if not self._client or not self.base_url:
            return None
        try:
            resp = await self._client.get(f"/api/v1/runs/{task_id}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("runtime get_task failed: %s", exc)
            return None
