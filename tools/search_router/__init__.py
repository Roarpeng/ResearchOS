"""Search Router — unified search facade (ADR-0007)."""

from tools.search_router.router import SearchRouter, SearchBudget
from tools.search_router.schema import SearchHit, SearchQueryResult

__all__ = ["SearchRouter", "SearchBudget", "SearchHit", "SearchQueryResult"]
