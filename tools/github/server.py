"""Read-only GitHub MCP — github.get_file / github.search_code.

Per docs/mcp/05-knowledge-tools.md (GitHub 交叉) and 07 (github:read scope):
fetched text is meant to flow through documents + parser into the knowledge
base, never straight into the vector store without provenance.
"""

from __future__ import annotations

import base64
import os
from typing import Any

import httpx

from tools._mcp_compat import create_mcp_server
from tools.security import SecurityError, redact_secrets

mcp = create_mcp_server("github")

_ALLOWED_HOSTS = ("api.github.com", "raw.githubusercontent.com", "github.com")
_MAX_BYTES = 512 * 1024


def _token() -> str:
    return os.environ.get("GITHUB_TOKEN", "").strip()


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ResearchOS-GitHub/0.1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = _token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _guard(url: str) -> None:
    host = url.split("/")[2].lower() if "://" in url else ""
    if host not in _ALLOWED_HOSTS:
        raise SecurityError("egress_denied", f"host {host!r} outside GitHub allowlist")


@mcp.tool(name="github.get_file")
def github_get_file(repo: str, path: str, ref: str = "HEAD") -> dict[str, Any]:
    """Fetch one file's text from a public (or token-readable) GitHub repo."""
    if not repo or not path:
        return {"ok": False, "error": "invalid_argument", "detail": "repo and path required"}
    url = f"https://api.github.com/repos/{repo.strip('/')}/contents/{path.lstrip('/')}"
    if ref not in {"HEAD", ""}:
        url += f"?ref={ref}"
    try:
        _guard(url)
    except SecurityError as exc:
        return {"ok": False, "error": exc.code, "detail": exc.detail}
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            resp = client.get(url, headers=_headers())
        if resp.status_code == 404:
            return {"ok": False, "error": "not_found", "repo": repo, "path": path}
        resp.raise_for_status()
        data = resp.json()
        if data.get("encoding") == "base64":
            text = base64.b64decode(data.get("content") or "").decode("utf-8", "replace")
        else:
            download = data.get("download_url")
            if not download:
                return {"ok": False, "error": "unsupported_payload"}
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                raw = client.get(download)
            raw.raise_for_status()
            text = raw.text
        return {
            "ok": True,
            "repo": repo,
            "path": path,
            "ref": ref,
            "sha": data.get("sha"),
            "bytes": len(text.encode("utf-8")),
            "text": redact_secrets(text[:200_000]),
            "ephemeral_hint": "route through documents+parser for provenance",
        }
    except SecurityError as exc:
        return {"ok": False, "error": exc.code, "detail": exc.detail}
    except Exception as exc:  # noqa: BLE001 — degrade cleanly
        return {"ok": False, "error": "github_failed", "detail": redact_secrets(str(exc))[:300]}


@mcp.tool(name="github.search_code")
def github_search_code(query: str, limit: int = 10) -> dict[str, Any]:
    """Code search (requires GITHUB_TOKEN; GitHub requires auth for code search)."""
    if not (query or "").strip():
        return {"ok": False, "error": "invalid_argument", "detail": "query required"}
    token = _token()
    if not token:
        return {
            "ok": False,
            "error": "github_token_required",
            "detail": "set GITHUB_TOKEN to enable code search",
        }
    url = "https://api.github.com/search/code"
    try:
        _guard(url)
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(
                url,
                params={"q": query, "per_page": max(1, min(int(limit), 50))},
                headers=_headers(),
            )
        resp.raise_for_status()
        data = resp.json()
        items = [
            {
                "repo": item.get("repository", {}).get("full_name"),
                "path": item.get("path"),
                "sha": item.get("sha"),
                "html_url": item.get("html_url"),
            }
            for item in (data.get("items") or [])[:limit]
        ]
        return {"ok": True, "total_count": data.get("total_count", len(items)), "items": items}
    except SecurityError as exc:
        return {"ok": False, "error": exc.code, "detail": exc.detail}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "github_failed", "detail": redact_secrets(str(exc))[:300]}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
