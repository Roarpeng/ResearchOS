"""MCP server for search-router (search.query / search.fetch / search.providers)."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from tools.search_router.providers import available_providers
from tools.search_router.router import SearchRouter

mcp = FastMCP("search-router")
_router = SearchRouter()


@mcp.tool(name="search.query")
def search_query(
    query: str,
    limit: int = 8,
    provider: str = "auto",
    lang: str = "zh-CN",
) -> dict[str, Any]:
    """Unified search: returns normalized SearchHit list."""
    result = _router.query(query, limit=limit, provider=provider, lang=lang)  # type: ignore[arg-type]
    return json.loads(result.model_dump_json())


@mcp.tool(name="search.fetch")
def search_fetch(result_id: str | None = None, url: str | None = None) -> dict[str, Any]:
    """Fetch a normalized document snippet by result id or URL."""
    return _router.fetch(result_id=result_id, url=url)


@mcp.tool(name="search.providers")
def search_providers() -> dict[str, Any]:
    """List provider availability and routing order."""
    return {
        "providers": available_providers(),
        "route": _router.explain_route("auto"),
    }


@mcp.tool(name="search.explain_route")
def search_explain_route(provider: str = "auto") -> dict[str, Any]:
    return _router.explain_route(provider)  # type: ignore[arg-type]


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
