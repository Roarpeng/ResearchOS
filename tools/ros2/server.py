"""mcp-ros2 server — read-only ROS2 workspace introspection (Phase 5 industrial).

Aligned with docs/industrial/01-robotics-and-ros2.md:

- `ros2.workspace.list_packages` / `ros2.pkg.inspect` / `ros2.interface.show` — read-only
- `ros2.docs.search` — local knowledge.pipeline placeholder (empty hits on failure)
- `ros2.codegen.suggest` / `ros2.apply_patch` — disabled by default; never write files
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from industrial.connectors.ros2_docs import Ros2WorkspaceConnector
from tools._mcp_compat import create_mcp_server

mcp = create_mcp_server("ros2")

_connector = Ros2WorkspaceConnector()


@mcp.tool(name="ros2.workspace.list_packages")
def ros2_workspace_list_packages(workspace_root: str) -> dict[str, Any]:
    """List ROS2 packages under a workspace root (recursively scans package.xml)."""
    root = Path(workspace_root).expanduser()
    if not root.is_dir():
        return {
            "ok": False,
            "readonly": True,
            "error": "workspace_not_found",
            "workspace_root": str(workspace_root),
        }
    packages = _connector.list_packages(str(root))
    return {
        "ok": True,
        "readonly": True,
        "workspace_root": str(root),
        "count": len(packages),
        "packages": packages,
    }


@mcp.tool(name="ros2.pkg.inspect")
def ros2_pkg_inspect(workspace_root: str, package_name: str) -> dict[str, Any]:
    """Inspect one package: include/msg/srv/action contents and launch file list."""
    root = Path(workspace_root).expanduser()
    if not root.is_dir():
        return {
            "ok": False,
            "readonly": True,
            "error": "workspace_not_found",
            "workspace_root": str(workspace_root),
        }
    info = _connector.inspect_package(str(root), package_name)
    if info is None:
        return {"ok": False, "readonly": True, "error": "package_not_found", "package": package_name}
    return {"ok": True, "readonly": True, **info}


@mcp.tool(name="ros2.interface.show")
def ros2_interface_show(
    workspace_root: str,
    package_name: str,
    interface_name: str,
) -> dict[str, Any]:
    """Show a msg/srv/action definition as parsed field lines (read-only)."""
    root = Path(workspace_root).expanduser()
    if not root.is_dir():
        return {
            "ok": False,
            "readonly": True,
            "error": "workspace_not_found",
            "workspace_root": str(workspace_root),
        }
    info = _connector.show_interface(str(root), package_name, interface_name)
    if info is None:
        return {
            "ok": False,
            "readonly": True,
            "error": "interface_not_found",
            "package": package_name,
            "interface": interface_name,
        }
    return {"ok": True, "readonly": True, **info}


@mcp.tool(name="ros2.docs.search")
def ros2_docs_search(query: str, top_k: int = 10) -> dict[str, Any]:
    """Local ROS2 documentation retrieval placeholder (delegates to knowledge.pipeline.search)."""
    try:
        from knowledge.pipeline import KnowledgePipeline

        pack = KnowledgePipeline().search(query, top_k=max(1, min(int(top_k), 64)))
        hits = pack.get("passages") or []
        return {
            "ok": True,
            "readonly": True,
            "count": len(hits),
            "hits": hits,
            "placeholder": False,
        }
    except Exception:  # noqa: BLE001 — placeholder must never raise
        return {
            "ok": True,
            "readonly": True,
            "count": 0,
            "hits": [],
            "placeholder": True,
        }


@mcp.tool(name="ros2.codegen.suggest")
def ros2_codegen_suggest(**kwargs: Any) -> dict[str, Any]:
    """Codegen suggestion — disabled by default; advisory only, never writes files."""
    return {
        "ok": False,
        "readonly": True,
        "status": "not_enabled",
        "code": "ROS2_CODEGEN_DISABLED",
        "message": "Code generation is disabled in this read-only slice; no files are written.",
    }


@mcp.tool(name="ros2.apply_patch")
def ros2_apply_patch(**kwargs: Any) -> dict[str, Any]:
    """Apply a workspace patch — disabled by default; never writes files."""
    return {
        "ok": False,
        "readonly": True,
        "status": "not_enabled",
        "code": "ROS2_APPLY_PATCH_DISABLED",
        "message": "Workspace writes are disabled by default; patches must be merged manually.",
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
