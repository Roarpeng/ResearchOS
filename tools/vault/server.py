"""Vault MCP server — research-folder capture into the knowledge layer."""

from __future__ import annotations

from typing import Any

from tools._mcp_compat import create_mcp_server
from tools.vault import core

mcp = create_mcp_server("vault")

_WATCHERS: dict[str, core.VaultWatcher] = {}


@mcp.tool(name="vault.scan", description="List files under a research folder with support flags.")
def vault_scan(root: str) -> dict[str, Any]:
    entries = core.scan(root)
    return {
        "count": len(entries),
        "supported": sum(1 for e in entries if e.supported),
        "files": [{"path": e.path, "size": e.size, "supported": e.supported} for e in entries],
    }


@mcp.tool(
    name="vault.ingest",
    description="Ingest new/changed files under a folder into the knowledge layer (SHA256 dedup).",
)
def vault_ingest(root: str, workspace_id: str | None = None) -> dict[str, Any]:
    res = core.ingest(root, workspace_id=workspace_id)
    return {
        "scanned": res.scanned,
        "ingested": res.ingested,
        "skipped_unchanged": res.skipped_unchanged,
        "skipped_unsupported": res.skipped_unsupported,
        "failed": res.failed,
        "details": res.details,
    }


@mcp.tool(
    name="vault.watch",
    description="Start a background watcher that ingests new files under a folder periodically.",
)
def vault_watch(
    root: str,
    workspace_id: str | None = None,
    interval_s: float = 5.0,
) -> dict[str, Any]:
    key = str(core.Path(root))
    watcher = _WATCHERS.get(key)
    if watcher is None:
        watcher = core.VaultWatcher(root, workspace_id=workspace_id, interval=interval_s)
        _WATCHERS[key] = watcher
    return watcher.start()


@mcp.tool(name="vault.stop", description="Stop the background watcher for a folder.")
def vault_stop(root: str) -> dict[str, Any]:
    watcher = _WATCHERS.pop(str(core.Path(root)), None)
    if watcher is None:
        return {"ok": True, "stopped": False}
    return watcher.stop()


@mcp.tool(name="vault.capture", description="Quick capture: write a timestamped note into the folder inbox.")
def vault_capture(root: str, text: str, tag: str | None = None) -> dict[str, Any]:
    return core.append_note(root, text, tag=tag)


@mcp.tool(name="vault.import_chat", description="Import a chat transcript into per-turn Markdown notes.")
def vault_import_chat(root: str, text: str) -> dict[str, Any]:
    return core.import_chat_transcript(root, text)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
