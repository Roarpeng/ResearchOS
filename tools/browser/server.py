"""MCP stub server for browser/crawl tools."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from tools.browser.crawl import fetch

mcp = FastMCP("browser")


@mcp.tool(name="crawl.fetch")
def crawl_fetch(url: str, max_chars: int = 4000) -> dict[str, Any]:
    """Fetch page content (stub: placeholder HTML/text)."""
    return fetch(url, max_chars=max_chars)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
