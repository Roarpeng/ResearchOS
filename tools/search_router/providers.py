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


def tavily_search(query: str, limit: int = 8) -> list[SearchHit]:
    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY not set")

    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": limit,
        "include_answer": False,
    }
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


def searx_search(query: str, limit: int = 8) -> list[SearchHit]:
    base = os.environ.get("SEARXNG_BASE_URL", "").rstrip("/")
    if not base:
        raise RuntimeError("SEARXNG_BASE_URL not set")

    params: dict[str, Any] = {"q": query, "format": "json", "language": "en"}
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


PROVIDER_NAMES = ("mock", "tavily", "searxng")


def available_providers() -> dict[str, dict[str, Any]]:
    return {
        "mock": {"available": True, "requires": []},
        "tavily": {
            "available": bool(os.environ.get("TAVILY_API_KEY", "").strip()),
            "requires": ["TAVILY_API_KEY"],
        },
        "searxng": {
            "available": bool(os.environ.get("SEARXNG_BASE_URL", "").strip()),
            "requires": ["SEARXNG_BASE_URL"],
        },
    }
