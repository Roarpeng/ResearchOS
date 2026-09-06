"""Scholar MCP server — citation lookup + phantom-citation scan (lookup-only)."""

from __future__ import annotations

from typing import Any

from tools._mcp_compat import create_mcp_server
from tools.scholar import core

mcp = create_mcp_server("scholar")


@mcp.tool(
    name="scholar.resolve",
    description="Resolve a DOI to normalized metadata (Crossref, fallback OpenAlex).",
)
def scholar_resolve(doi: str) -> dict[str, Any]:
    item = core.resolve(doi)
    return {"ok": bool(item), "item": item}


@mcp.tool(
    name="scholar.lookup",
    description="Search Crossref for works matching a bibliographic query.",
)
def scholar_lookup(query: str, rows: int = 10) -> dict[str, Any]:
    return {"items": core.lookup(query, rows=rows)}


@mcp.tool(
    name="scholar.verify",
    description="Scan text or DOI list; flag phantom (unresolvable) citations.",
)
def scholar_verify(text: str) -> dict[str, Any]:
    return core.verify(text)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
