"""Documents MCP server — register metadata + put object (MinIO or local)."""

from __future__ import annotations

import base64
from typing import Any

from tools._mcp_compat import create_mcp_server
from knowledge.store import get_registry

mcp = create_mcp_server("documents")


@mcp.tool(name="documents.register")
def documents_register(
    title: str | None = None,
    filename: str | None = None,
    mime_type: str | None = None,
    workspace_id: str | None = None,
    url: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Register document metadata without uploading bytes."""
    meta = get_registry().documents.register(
        title=title,
        filename=filename,
        mime_type=mime_type,
        workspace_id=workspace_id,
        url=url,
        tags=tags,
    )
    return meta.model_dump(mode="json")


@mcp.tool(name="documents.upload")
def documents_upload(
    content_b64: str,
    filename: str,
    title: str | None = None,
    mime_type: str | None = None,
    workspace_id: str | None = None,
    doc_id: str | None = None,
) -> dict[str, Any]:
    """Upload raw bytes (base64) to MinIO or ./data/objects and register metadata."""
    data = base64.b64decode(content_b64)
    reg = get_registry().documents
    meta = reg.register(
        title=title,
        filename=filename,
        mime_type=mime_type,
        workspace_id=workspace_id,
        doc_id=doc_id,
    )
    meta = reg.put_bytes(meta.doc_id, data, filename=filename)
    return meta.model_dump(mode="json")


@mcp.tool(name="documents.get")
def documents_get(doc_id: str) -> dict[str, Any]:
    """Fetch document metadata by id."""
    meta = get_registry().documents.get(doc_id)
    if meta is None:
        return {"ok": False, "error": "not_found", "doc_id": doc_id}
    return {"ok": True, "document": meta.model_dump(mode="json")}


@mcp.tool(name="documents.list")
def documents_list(workspace_id: str | None = None) -> dict[str, Any]:
    docs = get_registry().documents.list(workspace_id=workspace_id)
    return {"documents": [d.model_dump(mode="json") for d in docs]}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
