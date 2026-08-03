"""Unit tests: SearchRouter mock provider."""

from __future__ import annotations

from tools.search_router.router import SearchBudget, SearchRouter


def test_search_router_mock_returns_normalized_hits():
    router = SearchRouter(budget=SearchBudget(max_queries=5, max_fetches=5))
    result = router.query("UR20 cobot force control", limit=3, provider="mock")
    assert result.ok is True
    assert result.provider_used == "mock"
    assert len(result.results) == 3
    hit = result.results[0]
    assert hit.id.startswith("hit_mock_")
    assert hit.title
    assert hit.url
    assert hit.snippet
    assert hit.raw_provider == "mock"


def test_search_router_budget_exhaustion():
    router = SearchRouter(budget=SearchBudget(max_queries=1, max_fetches=1))
    first = router.query("alpha", provider="mock")
    assert first.ok is True
    second = router.query("beta", provider="mock")
    assert second.ok is False
    assert "budget" in (second.error or "").lower()


def test_search_router_fetch_from_cache():
    router = SearchRouter()
    result = router.query("encoder IP rating", limit=1, provider="mock")
    hit_id = result.results[0].id
    fetched = router.fetch(result_id=hit_id)
    assert fetched["ok"] is True
    assert fetched["id"] == hit_id
