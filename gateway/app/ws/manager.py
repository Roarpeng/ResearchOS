"""In-memory WebSocket connection manager."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("researchos.gateway.ws")


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, task_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._rooms[task_id].add(websocket)
        logger.info("ws connected task_id=%s", task_id)

    async def disconnect(self, task_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            peers = self._rooms.get(task_id)
            if peers and websocket in peers:
                peers.discard(websocket)
            if peers is not None and not peers:
                self._rooms.pop(task_id, None)
        logger.info("ws disconnected task_id=%s", task_id)

    async def broadcast(self, task_id: str, message: dict[str, Any]) -> None:
        async with self._lock:
            peers = list(self._rooms.get(task_id, set()))
        for ws in peers:
            try:
                await ws.send_json(message)
            except Exception as exc:  # noqa: BLE001
                logger.debug("ws send failed: %s", exc)


manager = ConnectionManager()
