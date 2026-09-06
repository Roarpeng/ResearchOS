"""Plot MCP server — data → reproducible code → rendered PNG."""

from __future__ import annotations

from typing import Any

from tools._mcp_compat import create_mcp_server
from tools.plot import core

mcp = create_mcp_server("plot")


@mcp.tool(name="plot.columns", description="List columns and row count of a CSV/XLSX table.")
def plot_columns(path: str) -> dict[str, Any]:
    return core.read_columns(path)


@mcp.tool(
    name="plot.render",
    description="Generate reproducible matplotlib code and render a PNG from a data file.",
)
def plot_render(
    path: str,
    x: str,
    y: str,
    kind: str = "bar",
    title: str = "",
    out_dir: str | None = None,
) -> dict[str, Any]:
    return core.render(path, x, y, kind=kind, title=title, out_dir=out_dir)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
