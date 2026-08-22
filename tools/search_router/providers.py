"""Search provider adapters. Agents must not import vendor SDKs directly."""

from __future__ import annotations

import hashlib
import os
from typing import Any
from urllib.parse import quote_plus

import httpx

from tools.search_router.schema import SearchHit


def _hit_id(provider: str, url: str, title: str) -> str:
    digest = hashlib.sha256(f"{provider}|{url}|{title}".encode()).hexdigest()[:12]
    return f"hit_{provider}_{digest}"


def mock_search(query: str, limit: int = 8) -> list[SearchHit]:
    """Deterministic mock web results for offline / demo use."""
    q = query.strip() or "research"
    templates = [
        (
            f"{q} — Official overview",
            f"https://example.com/docs/{quote_plus(q[:40])}",
            f"Official documentation summarizing key facts about {q}.",
            0.92,
            "manufacturer",
        ),
        (
            f"{q} — Competitive landscape 2025",
            f"https://example.com/reports/{quote_plus(q[:40])}",
            f"Industry report covering competitors, pricing bands, and risks for {q}.",
            0.84,
            "report",
        ),
        (
            f"{q} — Technical whitepaper",
            f"https://example.com/whitepapers/{quote_plus(q[:40])}",
            f"Whitepaper with specifications, standards references, and measured data for {q}.",
            0.79,
            "whitepaper",
        ),
        (
            f"{q} — Safety & compliance notes",
            f"https://example.com/standards/{quote_plus(q[:40])}",
            f"Compliance notes and standard citations relevant to {q}.",
            0.71,
            "standard",
        ),
        (
            f"{q} — Market commentary",
            f"https://news.example.com/{quote_plus(q[:40])}",
            f"Secondary commentary on market positioning related to {q}.",
            0.55,
            "news",
        ),
    ]
    hits: list[SearchHit] = []
    for title, url, snippet, score, source in templates[: max(1, min(limit, len(templates)))]:
        hits.append(
            SearchHit(
                id=_hit_id("mock", url, title),
                title=title,
                url=url,
                source_id=url,
                snippet=snippet,
                score=score,
                source_type="web",
                raw_provider="mock",
                raw_ref={"source": source},
            )
        )
    return hits


def tavily_search(
    query: str,
    limit: int = 8,
    *,
    time_range: str | None = None,
) -> list[SearchHit]:
    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY not set")

    payload: dict[str, Any] = {
        "api_key": api_key,
        "query": query,
        "max_results": limit,
        "include_answer": False,
    }
    if time_range:
        payload["time_range"] = time_range
    with httpx.Client(timeout=30.0) as client:
        resp = client.post("https://api.tavily.com/search", json=payload)
        resp.raise_for_status()
        data = resp.json()

    hits: list[SearchHit] = []
    for item in data.get("results", [])[:limit]:
        url = item.get("url") or ""
        title = item.get("title") or url or "untitled"
        hits.append(
            SearchHit(
                id=_hit_id("tavily", url, title),
                title=title,
                url=url or None,
                source_id=url or None,
                snippet=item.get("content") or item.get("snippet") or "",
                score=float(item.get("score") or 0.5),
                source_type="web",
                published_at=item.get("published_date"),
                raw_provider="tavily",
            )
        )
    return hits


def brave_search(
    query: str,
    limit: int = 8,
    *,
    freshness: str | None = None,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    safesearch: str | None = None,
    country: str | None = None,
    search_lang: str | None = None,
) -> list[SearchHit]:
    """Brave Search API adapter (docs/mcp/02: 独立索引、地区/合规选项)."""
    api_key = os.environ.get("BRAVE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("BRAVE_API_KEY not set")

    q = query
    if include_domains:
        sites = " OR ".join(f"site:{d}" for d in include_domains)
        q = f"({q}) ({sites})"
    for domain in exclude_domains or []:
        q += f" -site:{domain}"

    freshness_map = {"day": "pd", "week": "pw", "month": "pm", "year": "py"}
    params: dict[str, Any] = {"q": q, "count": max(1, min(limit, 20))}
    if freshness and freshness != "any":
        if freshness not in freshness_map:
            raise ValueError(f"invalid freshness: {freshness}")
        params["freshness"] = freshness_map[freshness]
    if safesearch:
        params["safesearch"] = safesearch
    if country:
        params["country"] = country
    if search_lang:
        params["search_lang"] = search_lang

    with httpx.Client(timeout=30.0) as client:
        resp = client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params=params,
            headers={"X-Subscription-Token": api_key},
        )
        resp.raise_for_status()
        data = resp.json()

    hits: list[SearchHit] = []
    for item in (data.get("web") or {}).get("results", [])[:limit]:
        url = item.get("url") or ""
        title = item.get("title") or url or "untitled"
        meta = item.get("meta") or {}
        hits.append(
            SearchHit(
                id=_hit_id("brave", url, title),
                title=title,
                url=url or None,
                source_id=url or None,
                snippet=item.get("description") or "",
                score=float(item.get("score") or 0.5),
                source_type="web",
                published_at=item.get("age") or meta.get("date"),
                raw_provider="brave",
            )
        )
    return hits


def searx_search(
    query: str,
    limit: int = 8,
    *,
    language: str | None = None,
) -> list[SearchHit]:
    base = os.environ.get("SEARXNG_BASE_URL", "").rstrip("/")
    if not base:
        raise RuntimeError("SEARXNG_BASE_URL not set")

    params: dict[str, Any] = {
        "q": query,
        "format": "json",
        "language": language or "en",
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(f"{base}/search", params=params)
        resp.raise_for_status()
        data = resp.json()

    hits: list[SearchHit] = []
    for item in data.get("results", [])[:limit]:
        url = item.get("url") or ""
        title = item.get("title") or url or "untitled"
        hits.append(
            SearchHit(
                id=_hit_id("searx", url, title),
                title=title,
                url=url or None,
                source_id=url or None,
                snippet=item.get("content") or item.get("snippet") or "",
                score=float(item.get("score") or 0.5),
                source_type="web",
                published_at=item.get("publishedDate") or item.get("published_at"),
                raw_provider="searxng",
            )
        )
    return hits


PROVIDER_NAMES = ("mock", "tavily", "brave", "searxng")


def available_providers() -> dict[str, dict[str, Any]]:
    return {
        "mock": {"available": True, "requires": []},
        "tavily": {
            "available": bool(os.environ.get("TAVILY_API_KEY", "").strip()),
            "requires": ["TAVILY_API_KEY"],
        },
        "brave": {
            "available": bool(os.environ.get("BRAVE_API_KEY", "").strip()),
            "requires": ["BRAVE_API_KEY"],
        },
        "searxng": {
            "available": bool(os.environ.get("SEARXNG_BASE_URL", "").strip()),
            "requires": ["SEARXNG_BASE_URL"],
        },
    }
