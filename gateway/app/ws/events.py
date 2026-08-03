"""WebSocket event helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def server_event(
    *,
    task_id: str,
    event_type: str,
    seq: int,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "task_id": task_id,
        "event_type": event_type,
        "seq": seq,
        "payload": payload or {},
        "ts": datetime.now(timezone.utc).isoformat(),
    }
