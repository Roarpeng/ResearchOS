"""In-process SearchRouter with budget enforcement."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

from tools.search_router.providers import (
    available_providers,
    mock_search,
    searx_search,
    tavily_search,
)
from tools.search_router.schema import SearchHit, SearchQueryResult

ProviderName = Literal["auto", "mock", "tavily", "searxng"]


@dataclass
class SearchBudget:
    max_queries: int = 20
    used_queries: int = 0
    max_fetches: int = 40
    used_fetches: int = 0

    def remaining_queries(self) -> int:
        return max(0, self.max_queries - self.used_queries)

    def remaining_fetches(self) -> int:
        return max(0, self.max_fetches - self.used_fetches)


@dataclass
class SearchRouter:
    """Unified search entry used by Research Agent (in-process) and MCP server."""

    budget: SearchBudget = field(default_factory=SearchBudget)
    prefer_privacy: bool = False
    _fetch_cache: dict[str, SearchHit] = field(default_factory=dict)

    def explain_route(self, provider: ProviderName = "auto") -> dict[str, Any]:
        status = available_providers()
        order = self._fallback_order(provider)
        return {
            "requested": provider,
            "fallback_order": order,
            "providers": status,
        }

    def _fallback_order(self, provider: ProviderName) -> list[str]:
        status = available_providers()
        if provider != "auto":
            return [provider]

        order: list[str] = []
        if self.prefer_privacy and status["searxng"]["available"]:
            order.append("searxng")
        if status["tavily"]["available"]:
            order.append("tavily")
        if status["searxng"]["available"] and "searxng" not in order:
            order.append("searxng")
        order.append("mock")
        # de-dupe preserve order
        seen: set[str] = set()
        out: list[str] = []
        for name in order:
            if name not in seen:
                seen.add(name)
                out.append(name)
        return out

    def query(
        self,
        query: str,
        *,
        limit: int = 8,
        provider: ProviderName = "auto",
        lang: str | None = None,
        **_filters: Any,
    ) -> SearchQueryResult:
        _ = lang  # reserved for provider adapters
        if self.budget.remaining_queries() <= 0:
            return SearchQueryResult(
                ok=False,
                provider_used="none",
                error="search budget exhausted (max_queries)",
                diagnostics={"used_queries": self.budget.used_queries},
            )

        started = time.perf_counter()
        tried: list[str] = []
        last_error: str | None = None

        for name in self._fallback_order(provider):
            tried.append(name)
            try:
                hits = self._dispatch(name, query, limit)
                self.budget.used_queries += 1
                for hit in hits:
                    self._fetch_cache[hit.id] = hit
                latency_ms = int((time.perf_counter() - started) * 1000)
                return SearchQueryResult(
                    ok=True,
                    provider_used=name,
                    results=hits,
                    diagnostics={
                        "tried": tried,
                        "latency_ms": latency_ms,
                        "budget": {
                            "used_queries": self.budget.used_queries,
                            "max_queries": self.budget.max_queries,
                        },
                    },
                )
            except Exception as exc:  # noqa: BLE001 — provider isolation
                last_error = f"{name}: {exc}"
                continue

        self.budget.used_queries += 1
        return SearchQueryResult(
            ok=False,
            provider_used="none",
            error=last_error or "all providers failed",
            diagnostics={"tried": tried},
        )

    def fetch(self, result_id: str | None = None, url: str | None = None) -> dict[str, Any]:
        if self.budget.remaining_fetches() <= 0:
            return {"ok": False, "error": "search budget exhausted (max_fetches)"}

        self.budget.used_fetches += 1
        if result_id and result_id in self._fetch_cache:
            hit = self._fetch_cache[result_id]
            return {
                "ok": True,
                "id": hit.id,
                "title": hit.title,
                "url": hit.url,
                "snippet": hit.snippet,
                "content": hit.snippet,
            }

        if url:
            for hit in self._fetch_cache.values():
                if hit.url == url:
                    return {
                        "ok": True,
                        "id": hit.id,
                        "title": hit.title,
                        "url": hit.url,
                        "snippet": hit.snippet,
                        "content": hit.snippet,
                    }
            # lightweight placeholder fetch
            return {
                "ok": True,
                "id": f"fetch_{abs(hash(url)) % 10_000_000}",
                "title": url,
                "url": url,
                "snippet": f"Placeholder fetch for {url}",
                "content": f"Placeholder document body for {url}",
            }

        return {"ok": False, "error": "result_id or url required"}

    def _dispatch(self, name: str, query: str, limit: int) -> list[SearchHit]:
        if name == "mock":
            return mock_search(query, limit=limit)
        if name == "tavily":
            return tavily_search(query, limit=limit)
        if name == "searxng":
            return searx_search(query, limit=limit)
        raise ValueError(f"unknown provider: {name}")
