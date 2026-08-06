"""MCP client wrapper — in-process hello tool or stdio MCP server."""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

from runtime.researchos_runtime.settings import RuntimeSettings, get_settings
from tools.hello.echo import hello_echo

logger = logging.getLogger("researchos.runtime.mcp")


class MCPClient:
    """Thin wrapper around MCP tools used by the runtime."""

    def __init__(self, settings: RuntimeSettings | None = None) -> None:
        self.settings = settings or get_settings()

    def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        args = dict(arguments or {})
        if task_id and "task_id" not in args:
            args["task_id"] = task_id

        started = time.perf_counter()
        try:
            if name in ("hello.echo", "hello_echo", "echo"):
                result = self._call_hello_echo(args)
            elif name.startswith("plc."):
                result = self._call_plc(name, args)
            else:
                raise ValueError(f"Unsupported MCP tool: {name}")
            duration_ms = int((time.perf_counter() - started) * 1000)
            return {
                "ok": True,
                "tool": name,
                "result": result,
                "duration_ms": duration_ms,
            }
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.exception("MCP tool %s failed", name)
            return {
                "ok": False,
                "tool": name,
                "error": str(exc),
                "duration_ms": duration_ms,
            }

    def _call_hello_echo(self, args: dict[str, Any]) -> dict[str, Any]:
        mode = (self.settings.mcp_hello_mode or "inprocess").lower()
        message = str(args.get("message", "hello"))
        task_id = args.get("task_id")
        if mode == "stdio":
            return self._call_hello_stdio(message=message, task_id=task_id)
        return hello_echo(message, task_id=task_id)

    def _call_plc(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Dispatch plc.* tools to the in-process mcp-plc implementation."""
        from tools.plc import server as plc_server

        args = {k: v for k, v in args.items() if k != "task_id"}
        dispatch = {
            "plc.vendors.list": plc_server.plc_vendors_list,
            "plc.manual.search": plc_server.plc_manual_search,
            "plc.manual.get": plc_server.plc_manual_get,
            "plc.alarm.explain": plc_server.plc_alarm_explain,
            "plc.tia.analyze": plc_server.plc_tia_analyze,
            "plc.project.analyze": plc_server.plc_project_analyze,
            "plc.program.download": plc_server.plc_program_download,
            "plc.program.upload_suggest": plc_server.plc_program_upload_suggest,
        }
        fn = dispatch.get(name)
        if fn is None:
            raise ValueError(f"Unsupported PLC tool: {name}")
        return fn(**args)

    def _call_hello_stdio(self, *, message: str, task_id: str | None) -> dict[str, Any]:
        """Invoke tools/hello MCP server over stdio (sync helper)."""
        import anyio
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        root = Path(__file__).resolve().parents[2]
        server_script = root / "tools" / "hello" / "server.py"
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(server_script)],
            cwd=str(root),
        )

        async def _run() -> dict[str, Any]:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        "hello.echo",
                        {"message": message, "task_id": task_id},
                    )
                    texts: list[str] = []
                    for block in result.content or []:
                        text = getattr(block, "text", None)
                        if text:
                            texts.append(text)
                    joined = "\n".join(texts) if texts else "{}"
                    try:
                        return json.loads(joined)
                    except json.JSONDecodeError:
                        return {"ok": True, "raw": joined}

        return anyio.run(_run)


_default_client: MCPClient | None = None


def get_mcp_client(settings: RuntimeSettings | None = None) -> MCPClient:
    global _default_client
    if settings is not None:
        return MCPClient(settings)
    if _default_client is None:
        _default_client = MCPClient()
    return _default_client
