"""Public hub clients: official MCP Registry + Agent Skills (skills.sh / GitHub)."""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger("researchos.gateway.hub")

MCP_REGISTRY = "https://registry.modelcontextprotocol.io/v0.1/servers"
SKILLS_SH_API = "https://skills.sh/api/skills"
GITHUB_API = "https://api.github.com"

# Offline / network-failure fallbacks (well-known public entries)
MCP_FALLBACK: list[dict[str, Any]] = [
    {
        "name": "io.github.modelcontextprotocol/server-filesystem",
        "title": "Filesystem",
        "description": "Secure file operations with configurable access controls",
        "transport": "stdio",
        "command": "npx",
        "args": "-y @modelcontextprotocol/server-filesystem",
        "url": "",
        "source": "fallback",
        "hub": "mcp-registry",
    },
    {
        "name": "io.github.modelcontextprotocol/server-github",
        "title": "GitHub",
        "description": "Repository management, issues, PRs via GitHub API",
        "transport": "stdio",
        "command": "npx",
        "args": "-y @modelcontextprotocol/server-github",
        "url": "",
        "source": "fallback",
        "hub": "mcp-registry",
    },
    {
        "name": "io.github.modelcontextprotocol/server-memory",
        "title": "Memory",
        "description": "Knowledge graph memory for persistent agent context",
        "transport": "stdio",
        "command": "npx",
        "args": "-y @modelcontextprotocol/server-memory",
        "url": "",
        "source": "fallback",
        "hub": "mcp-registry",
    },
]

SKILL_FALLBACK: list[dict[str, Any]] = [
    {
        "id": "anthropics/skills/docx",
        "name": "docx",
        "description": "Create and edit Word documents (Anthropic skills)",
        "owner": "anthropics",
        "repo": "skills",
        "path": "skills/docx",
        "installs": 0,
        "hub": "skills-fallback",
        "source_url": "https://github.com/anthropics/skills/tree/main/skills/docx",
    },
    {
        "id": "anthropics/skills/pptx",
        "name": "pptx",
        "description": "Create and edit PowerPoint decks",
        "owner": "anthropics",
        "repo": "skills",
        "path": "skills/pptx",
        "installs": 0,
        "hub": "skills-fallback",
        "source_url": "https://github.com/anthropics/skills/tree/main/skills/pptx",
    },
    {
        "id": "anthropics/skills/xlsx",
        "name": "xlsx",
        "description": "Create and edit Excel workbooks",
        "owner": "anthropics",
        "repo": "skills",
        "path": "skills/xlsx",
        "installs": 0,
        "hub": "skills-fallback",
        "source_url": "https://github.com/anthropics/skills/tree/main/skills/xlsx",
    },
    {
        "id": "anthropics/skills/pdf",
        "name": "pdf",
        "description": "PDF creation and extraction helpers",
        "owner": "anthropics",
        "repo": "skills",
        "path": "skills/pdf",
        "installs": 0,
        "hub": "skills-fallback",
        "source_url": "https://github.com/anthropics/skills/tree/main/skills/pdf",
    },
]


def _http_get_json(url: str, *, timeout: float = 20.0, headers: dict[str, str] | None = None) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "ResearchOS-HubClient/1.0",
            **(headers or {}),
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _http_get_text(url: str, *, timeout: float = 20.0) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "ResearchOS-HubClient/1.0", "Accept": "*/*"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read().decode("utf-8", errors="replace")


def _normalize_mcp_entry(item: dict[str, Any]) -> dict[str, Any] | None:
    server = item.get("server") if isinstance(item.get("server"), dict) else item
    if not isinstance(server, dict):
        return None
    name = str(server.get("name") or "").strip()
    if not name:
        return None
    title = str(server.get("title") or name.split("/")[-1])
    description = str(server.get("description") or "")
    remotes = server.get("remotes") or []
    packages = server.get("packages") or []

    transport = "stdio"
    command = ""
    args = ""
    url = ""

    if isinstance(packages, list) and packages:
        pkg = packages[0] if isinstance(packages[0], dict) else {}
        registry = str(pkg.get("registryType") or pkg.get("registry_type") or "").lower()
        identifier = str(pkg.get("identifier") or pkg.get("name") or "")
        runtime = str(pkg.get("runtimeHint") or pkg.get("runtime") or "")
        if registry in {"npm", "node"} or identifier.startswith("@"):
            transport = "stdio"
            command = "npx"
            args = f"-y {identifier}".strip()
        elif registry in {"pypi", "python"} or runtime.startswith("uvx") or runtime.startswith("pip"):
            transport = "stdio"
            command = "uvx"
            args = identifier
        elif identifier:
            transport = "stdio"
            command = "npx"
            args = f"-y {identifier}"

    if isinstance(remotes, list) and remotes and not command:
        remote = remotes[0] if isinstance(remotes[0], dict) else {}
        rtype = str(remote.get("type") or "http").lower()
        url = str(remote.get("url") or "")
        if "sse" in rtype:
            transport = "sse"
        elif "http" in rtype or "streamable" in rtype:
            transport = "http"
        else:
            transport = rtype or "http"

    return {
        "name": name,
        "title": title,
        "description": description[:400],
        "transport": transport,
        "command": command,
        "args": args,
        "url": url,
        "version": str(server.get("version") or ""),
        "repository": ((server.get("repository") or {}) if isinstance(server.get("repository"), dict) else {}).get(
            "url"
        ),
        "hub": "mcp-registry",
        "source": "live",
        "raw": {"has_packages": bool(packages), "has_remotes": bool(remotes)},
    }


def search_mcp_hub(query: str = "", *, limit: int = 20) -> dict[str, Any]:
    q = (query or "").strip()
    params = {"limit": str(max(1, min(limit, 50)))}
    if q:
        params["search"] = q
    url = f"{MCP_REGISTRY}?{urllib.parse.urlencode(params)}"
    try:
        data = _http_get_json(url)
        servers = data.get("servers") if isinstance(data, dict) else []
        items = []
        for raw in servers or []:
            norm = _normalize_mcp_entry(raw if isinstance(raw, dict) else {})
            if norm:
                items.append(norm)
        return {
            "hub": "registry.modelcontextprotocol.io",
            "query": q,
            "count": len(items),
            "items": items[:limit],
            "offline": False,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("MCP hub search failed: %s", exc)
        ql = q.lower()
        items = [
            x
            for x in MCP_FALLBACK
            if not ql or ql in x["name"].lower() or ql in x["description"].lower() or ql in x["title"].lower()
        ]
        return {
            "hub": "registry.modelcontextprotocol.io",
            "query": q,
            "count": len(items),
            "items": items[:limit],
            "offline": True,
            "warning": f"hub_unreachable:{exc}",
        }


def search_skills_hub(query: str = "", *, limit: int = 20) -> dict[str, Any]:
    q = (query or "").strip()
    # Prefer skills.sh open API; fall back to curated Anthropic skills list.
    try:
        params = urllib.parse.urlencode({"query": q or "agent", "limit": str(max(1, min(limit, 50)))})
        data = _http_get_json(f"{SKILLS_SH_API}?{params}")
        rows = data.get("skills") or data.get("items") or data.get("data") or data
        if not isinstance(rows, list):
            rows = []
        items = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or row.get("skillId") or row.get("id") or "").strip()
            if not name:
                continue
            items.append(
                {
                    "id": str(row.get("id") or f"{row.get('owner','')}/{row.get('repo','')}/{name}"),
                    "name": name,
                    "description": str(row.get("description") or "")[:400],
                    "owner": str(row.get("owner") or ""),
                    "repo": str(row.get("repo") or ""),
                    "path": str(row.get("path") or row.get("skillPath") or ""),
                    "installs": int(row.get("installs") or row.get("installCount") or 0),
                    "hub": "skills.sh",
                    "source_url": str(row.get("url") or row.get("html_url") or ""),
                    "source": "live",
                }
            )
        if items:
            return {
                "hub": "skills.sh",
                "query": q,
                "count": len(items),
                "items": items[:limit],
                "offline": False,
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("skills.sh search failed: %s", exc)

    ql = q.lower()
    items = [
        x
        for x in SKILL_FALLBACK
        if not ql or ql in x["name"].lower() or ql in x["description"].lower()
    ]
    return {
        "hub": "skills.sh+github-fallback",
        "query": q,
        "count": len(items),
        "items": items[:limit],
        "offline": True,
        "warning": "skills_hub_unreachable_or_empty",
    }


def install_mcp_from_hub(item: dict[str, Any]) -> dict[str, Any]:
    """Map hub item → agent workspace MCP server record (metadata only; no code exec)."""
    name = str(item.get("name") or item.get("title") or "").strip()
    if not name:
        raise ValueError("MCP name required")
    short = name.split("/")[-1]
    return {
        "id": f"mcp_{uuid4().hex[:10]}",
        "name": short[:128],
        "description": str(item.get("description") or name)[:500],
        "enabled": True,
        "transport": str(item.get("transport") or "stdio")[:32],
        "command": str(item.get("command") or "")[:512],
        "args": str(item.get("args") or "")[:512],
        "url": str(item.get("url") or "")[:512],
        "source": "hub",
        "hub_name": name[:256],
    }


def _safe_skill_dirname(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", name.strip()).strip("-").lower()
    return cleaned[:64] or f"skill-{uuid4().hex[:8]}"


def install_skill_from_hub(
    item: dict[str, Any],
    *,
    skills_root: Path | None = None,
) -> dict[str, Any]:
    """Download SKILL.md into .agents/skills/<name>/ and return workspace skill record."""
    name = str(item.get("name") or "").strip()
    if not name:
        raise ValueError("skill name required")
    owner = str(item.get("owner") or "anthropics")
    repo = str(item.get("repo") or "skills")
    rel = str(item.get("path") or f"skills/{name}").strip("/")
    dirname = _safe_skill_dirname(name)
    root = skills_root or Path.cwd() / ".agents" / "skills"
    dest_dir = root / dirname
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "SKILL.md"

    candidates = [
        f"https://raw.githubusercontent.com/{owner}/{repo}/main/{rel}/SKILL.md",
        f"https://raw.githubusercontent.com/{owner}/{repo}/master/{rel}/SKILL.md",
        f"https://raw.githubusercontent.com/{owner}/{repo}/main/{name}/SKILL.md",
    ]
    if item.get("content_url"):
        candidates.insert(0, str(item["content_url"]))

    content = ""
    last_err: Exception | None = None
    for url in candidates:
        try:
            content = _http_get_text(url)
            if content.strip():
                break
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            continue
    if not content.strip():
        # Write a stub that points to the hub source so local agent can still see the skill.
        content = (
            f"---\nname: {dirname}\ndescription: {item.get('description') or name}\n---\n\n"
            f"# {name}\n\n"
            f"在线安装占位：未能拉取远程 SKILL.md"
            + (f"（{last_err}）" if last_err else "")
            + f"。\n\n来源：https://github.com/{owner}/{repo}/tree/main/{rel}\n"
        )
        logger.warning("skill content download failed for %s: %s", name, last_err)

    dest.write_text(content, encoding="utf-8")
    return {
        "id": f"skill_{uuid4().hex[:10]}",
        "name": dirname,
        "description": str(item.get("description") or name)[:500],
        "enabled": True,
        "path": str(dest_dir),
        "source": "hub",
        "hub_id": str(item.get("id") or f"{owner}/{repo}/{name}"),
    }
