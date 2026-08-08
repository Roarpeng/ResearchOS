"""Persist agent tools, MCP servers, and skills for ResearchOS settings UI."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from gateway.app.config import Settings, get_settings

logger = logging.getLogger("researchos.gateway.agent_workspace")

DEFAULT_TOOLS: list[dict[str, Any]] = [
    {
        "id": "tool_web_search",
        "name": "web_search",
        "description": "联网检索公开资料",
        "enabled": True,
    },
    {
        "id": "tool_knowledge_search",
        "name": "knowledge_search",
        "description": "检索已上传的知识库资料",
        "enabled": True,
    },
    {
        "id": "tool_plc_query",
        "name": "plc_query",
        "description": "查询已解析的 PLC 知识图谱",
        "enabled": True,
    },
]


def _path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    override = os.getenv("AGENT_WORKSPACE_SETTINGS_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    base = Path(settings.plc_work_dir or tempfile.gettempdir()) / "researchos_settings"
    base.mkdir(parents=True, exist_ok=True)
    return base / "agent_workspace.json"


def _load_raw(settings: Settings | None = None) -> dict[str, Any]:
    path = _path(settings)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        logger.warning("failed to read agent workspace settings %s", path)
        return {}


def _save_raw(data: dict[str, Any], settings: Settings | None = None) -> None:
    path = _path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_item(item: dict[str, Any], *, kind: str) -> dict[str, Any]:
    name = str(item.get("name") or "").strip()
    if not name:
        raise ValueError(f"{kind} name required")
    out: dict[str, Any] = {
        "id": str(item.get("id") or f"{kind}_{uuid4().hex[:10]}"),
        "name": name[:128],
        "description": str(item.get("description") or "")[:500],
        "enabled": bool(item.get("enabled", True)),
    }
    if kind == "tool":
        out["command"] = str(item.get("command") or "")[:256]
    if kind == "mcp":
        out["transport"] = str(item.get("transport") or "stdio")[:32]
        out["command"] = str(item.get("command") or "")[:512]
        out["url"] = str(item.get("url") or "")[:512]
        out["args"] = str(item.get("args") or "")[:512]
        out["source"] = str(item.get("source") or "")[:64]
        out["hub_name"] = str(item.get("hub_name") or "")[:256]
    if kind == "skill":
        out["path"] = str(item.get("path") or "")[:512]
        out["source"] = str(item.get("source") or "local")[:64]
        out["hub_id"] = str(item.get("hub_id") or "")[:256]
    return out


def get_agent_workspace_settings(settings: Settings | None = None) -> dict[str, Any]:
    raw = _load_raw(settings)
    tools = raw.get("tools")
    if not isinstance(tools, list) or not tools:
        tools = list(DEFAULT_TOOLS)
    mcp = raw.get("mcp_servers") if isinstance(raw.get("mcp_servers"), list) else []
    skills = raw.get("skills") if isinstance(raw.get("skills"), list) else []
    return {
        "tools": [t for t in tools if isinstance(t, dict)],
        "mcp_servers": [m for m in mcp if isinstance(m, dict)],
        "skills": [s for s in skills if isinstance(s, dict)],
    }


def update_agent_workspace_settings(
    patch: dict[str, Any],
    settings: Settings | None = None,
) -> dict[str, Any]:
    current = get_agent_workspace_settings(settings)
    if "tools" in patch and patch["tools"] is not None:
        current["tools"] = [_normalize_item(dict(t), kind="tool") for t in patch["tools"]]
    if "mcp_servers" in patch and patch["mcp_servers"] is not None:
        current["mcp_servers"] = [
            _normalize_item(dict(m), kind="mcp") for m in patch["mcp_servers"]
        ]
    if "skills" in patch and patch["skills"] is not None:
        current["skills"] = [_normalize_item(dict(s), kind="skill") for s in patch["skills"]]
    _save_raw(current, settings)
    return current
