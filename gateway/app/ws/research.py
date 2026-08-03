"""WebSocket research stream — polls Runtime events and forwards to clients."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from gateway.app.config import get_settings
from gateway.app.services import store as mem
from gateway.app.ws.events import server_event
from gateway.app.ws.manager import manager

logger = logging.getLogger("researchos.gateway.ws.research")

router = APIRouter(tags=["websocket"])

_POLL_INTERVAL = 2.0  # seconds between runtime polls


async def _poll_runtime_events(
    task_id: str,
    stop_event: asyncio.Event,
) -> None:
    """Background task: poll runtime for state updates and broadcast via WS."""
    seq = 0
    last_status: str | None = None
    while not stop_event.is_set():
        try:
            task = mem.store.tasks.get(task_id)
            if not task:
                await asyncio.sleep(_POLL_INTERVAL)
                continue

            # Check runtime for updates if we have a runtime client
            runtime = None
            # Access runtime client from app state is not available here,
            # so we rely on task store updates from the REST endpoint.
            current_status = task.get("status", "queued")
            if current_status != last_status:
                seq += 1
                await manager.broadcast(
                    task_id,
                    server_event(
                        task_id=task_id,
                        event_type="task.status",
                        seq=seq,
                        payload={"status": current_status},
                    ),
                )
                last_status = current_status

            # Broadcast result if available
            result = task.get("result")
            if result and current_status in ("completed", "failed", "cancelled"):
                seq += 1
                await manager.broadcast(
                    task_id,
                    server_event(
                        task_id=task_id,
                        event_type="task.completed",
                        seq=seq,
                        payload={
                            "status": current_status,
                            "has_result": bool(result),
                        },
                    ),
                )
                # Terminal state — stop polling
                break

        except Exception as exc:  # noqa: BLE001
            logger.debug("ws poll error task_id=%s: %s", task_id, exc)

        await asyncio.sleep(_POLL_INTERVAL)


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

    authed = False
    last_seq = 0
    if isinstance(first, dict) and first.get("type") == "auth":
        token = first.get("token")
        if not settings.is_dev and not token:
            await websocket.close(code=4401)
            await manager.disconnect(task_id, websocket)
            return
        last_seq = int(first.get("last_seq") or 0)
        authed = True
        await websocket.send_json(
            {
                "type": "auth_ok",
                "task_id": task_id,
                "server_time": datetime.now(timezone.utc).isoformat(),
                "replayed_from": last_seq,
            }
        )
        # Send current task snapshot if available
        task = mem.store.tasks.get(task_id)
        if task:
            await websocket.send_json(
                server_event(
                    task_id=task_id,
                    event_type="task.snapshot",
                    seq=last_seq + 1,
                    payload={
                        "status": task.get("status", "queued"),
                        "query": task.get("query", ""),
                        "mode": task.get("mode", "deep"),
                    },
                )
            )
    elif isinstance(first, dict):
        # Accept non-auth first message in dev for easier smoke testing
        if settings.is_dev:
            authed = True
        else:
            await websocket.close(code=4401)
            await manager.disconnect(task_id, websocket)
            return
    else:
        if not settings.is_dev:
            await websocket.close(code=4401)
            await manager.disconnect(task_id, websocket)
            return

    # Start background polling for runtime events
    stop_event = asyncio.Event()
    poll_task = asyncio.create_task(_poll_runtime_events(task_id, stop_event))

    try:
        while True:
            msg = await websocket.receive_json()
            if isinstance(msg, dict):
                msg_type = msg.get("type")
                if msg_type == "pong":
                    continue
                if msg_type == "ping":
                    await websocket.send_json(
                        {"type": "pong", "ts": datetime.now(timezone.utc).isoformat()}
                    )
                elif msg_type == "resume":
                    # Client can trigger resume via WS
                    await websocket.send_json(
                        server_event(
                            task_id=task_id,
                            event_type="resume.requested",
                            seq=0,
                            payload={
                                "resolution": msg.get("resolution", "approve"),
                                "interrupt_id": msg.get("interrupt_id"),
                            },
                        )
                    )
    except WebSocketDisconnect:
        logger.debug("client disconnected task_id=%s", task_id)
    finally:
        stop_event.set()
        poll_task.cancel()
        try:
            await poll_task
        except asyncio.CancelledError:
            pass
        await manager.disconnect(task_id, websocket)
