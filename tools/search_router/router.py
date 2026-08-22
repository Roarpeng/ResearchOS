"""In-process SearchRouter with budget enforcement."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

from tools.search_router.providers import (
    available_providers,
    brave_search,
    mock_search,
    searx_search,
    tavily_search,
)
from tools.search_router.schema import SearchHit, SearchQueryResult

ProviderName = Literal["auto", "mock", "tavily", "brave", "searxng"]


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
        if status["brave"]["available"]:
            order.append("brave")
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
        freshness: str | None = None,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        safesearch: str | None = None,
        **_filters: Any,
    ) -> SearchQueryResult:
        """Search with docs/mcp/02 options (freshness/domain/safesearch passthrough)."""
        opts: dict[str, Any] = {
            "lang": lang,
            "freshness": freshness,
            "include_domains": include_domains,
            "exclude_domains": exclude_domains,
            "safesearch": safesearch,
        }
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
                hits = self._dispatch(name, query, limit, opts)
                hits = self._apply_domain_filters(
                    hits,
                    include_domains=include_domains,
                    exclude_domains=exclude_domains,
                )
                if not hits and (include_domains or exclude_domains):
                    # Provider results fully filtered out — try next provider.
                    continue
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

    @staticmethod
    def _apply_domain_filters(
        hits: list[SearchHit],
        *,
        include_domains: list[str] | None,
        exclude_domains: list[str] | None,
    ) -> list[SearchHit]:
        """Normalized domain constraints applied on every provider's hits."""

        def host_of(url: str | None) -> str:
            if not url:
                return ""
            return url.split("/")[2].lower() if "://" in url else url.lower()

        inc = [d.lower().lstrip(".") for d in (include_domains or [])]
        exc = [d.lower().lstrip(".") for d in (exclude_domains or [])]
        out: list[SearchHit] = []
        for hit in hits:
            host = host_of(hit.url)
            if exc and any(host == d or host.endswith("." + d) for d in exc):
                continue
            if inc and not any(host == d or host.endswith("." + d) for d in inc):
                continue
            out.append(hit)
        return out

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

    def _dispatch(
        self,
        name: str,
        query: str,
        limit: int,
        opts: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        opts = opts or {}
        if name == "mock":
            return mock_search(query, limit=limit)
        if name == "tavily":
            freshness = opts.get("freshness")
            return tavily_search(
                query,
                limit=limit,
                time_range=freshness if freshness in {"day", "week", "month", "year"} else None,
            )
        if name == "brave":
            return brave_search(
                query,
                limit=limit,
                freshness=opts.get("freshness"),
                include_domains=opts.get("include_domains"),
                exclude_domains=opts.get("exclude_domains"),
                safesearch=opts.get("safesearch"),
            )
        if name == "searxng":
            lang = opts.get("lang")
            return searx_search(query, limit=limit, language=lang)  # type: ignore[arg-type]
        raise ValueError(f"unknown provider: {name}")
