"""WebSocket research stream endpoint."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from gateway.app.config import get_settings
from gateway.app.services import store as mem
from gateway.app.ws.events import server_event
from gateway.app.ws.manager import manager

logger = logging.getLogger("researchos.gateway.ws.research")

router = APIRouter(tags=["websocket"])


@router.websocket("/api/v1/ws/research/{task_id}")
async def research_ws(websocket: WebSocket, task_id: str) -> None:
    settings = get_settings()
    await manager.connect(task_id, websocket)

    # Optional first-frame auth (recommended by docs)
    try:
        first = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
    except (TimeoutError, WebSocketDisconnect):
        await websocket.close(code=4401)
        await manager.disconnect(task_id, websocket)
        return

    if isinstance(first, dict) and first.get("type") == "auth":
        token = first.get("token")
        if not settings.is_dev and not token:
            await websocket.close(code=4401)
            await manager.disconnect(task_id, websocket)
            return
        last_seq = int(first.get("last_seq") or 0)
        await websocket.send_json(
            {
                "type": "auth_ok",
                "task_id": task_id,
                "server_time": datetime.now(timezone.utc).isoformat(),
                "replayed_from": last_seq,
            }
        )
        # Phase 1: emit a stub status snapshot if task exists locally
        task = mem.store.tasks.get(task_id)
        if task:
            await websocket.send_json(
                server_event(
                    task_id=task_id,
                    event_type="task.status",
                    seq=last_seq + 1,
                    payload={"status": task.get("status", "queued")},
                )
            )
    else:
        # Accept non-auth first message in dev for easier smoke testing
        if not settings.is_dev:
            await websocket.close(code=4401)
            await manager.disconnect(task_id, websocket)
            return

    try:
        while True:
            msg = await websocket.receive_json()
            if isinstance(msg, dict) and msg.get("type") == "pong":
                continue
            if isinstance(msg, dict) and msg.get("type") == "ping":
                await websocket.send_json(
                    {"type": "pong", "ts": datetime.now(timezone.utc).isoformat()}
                )
    except WebSocketDisconnect:
        logger.debug("client disconnected task_id=%s", task_id)
    finally:
        await manager.disconnect(task_id, websocket)
