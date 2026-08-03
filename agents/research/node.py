"""Research Agent node: SearchRouter → evidence[] (+ optional crawl stub)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from runtime.researchos_runtime.state import Budgets, TaskState
from tools.browser.crawl import fetch as crawl_fetch
from tools.search_router.router import SearchBudget, SearchRouter


def _budgets(state: TaskState) -> Budgets:
    return dict(state.get("budgets") or {})  # type: ignore[return-value]


def run(state: TaskState) -> dict[str, Any]:
    goal = state.get("goal") or {}
    query = (
        goal.get("normalized_objective")
        or goal.get("raw_query")
        or "research topic"
    )
    budgets = _budgets(state)
    max_tool = int(budgets.get("max_tool_calls") or 40)
    used_tool = int(budgets.get("used_tool_calls") or 0)
    remaining = max(0, max_tool - used_tool)
    limit = min(5, remaining or 1)

    router = SearchRouter(
        budget=SearchBudget(
            max_queries=max(1, remaining),
            used_queries=0,
            max_fetches=max(1, remaining),
        )
    )
    result = router.query(query, limit=limit, provider="auto")

    evidence: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()

    traces.append(
        {
            "tool": "search.query",
            "args": {"query": query, "limit": limit},
            "result_summary": (
                f"ok={result.ok} provider={result.provider_used} n={len(result.results)}"
            ),
            "ok": result.ok,
            "duration_ms": int((result.diagnostics or {}).get("latency_ms") or 0),
        }
    )

    for idx, hit in enumerate(result.results, start=1):
        eid = f"ev_{state.get('task_id', 'task')}_{idx}"
        content = hit.snippet
        # Optionally enrich first hit via crawl stub
        if idx == 1 and hit.url:
            page = crawl_fetch(hit.url)
            content = page.get("text") or content
            traces.append(
                {
                    "tool": "crawl.fetch",
                    "args": {"url": hit.url},
                    "result_summary": f"stub={page.get('stub')} title={page.get('title')}",
                    "ok": bool(page.get("ok")),
                    "duration_ms": 0,
                }
            )

        evidence.append(
            {
                "id": eid,
                "source_id": hit.source_id or hit.url or hit.id,
                "title": hit.title,
                "content": content,
                "url": hit.url or "",
                "locator": hit.id,
                "score": hit.score,
                "meta": {
                    "retrieved_at": now,
                    "retrieved_by": "research",
                    "provider": hit.raw_provider,
                    "source_type": hit.source_type,
                    "hit_id": hit.id,
                },
            }
        )

    used_delta = 1 + (1 if evidence and evidence[0].get("url") else 0)
    new_budgets = {
        **budgets,
        "used_tool_calls": used_tool + used_delta,
        "used_web_pages": int(budgets.get("used_web_pages") or 0)
        + (1 if evidence else 0),
    }

    events = [
        {
            "type": "research.evidence_appended",
            "task_id": state.get("task_id", ""),
            "payload": {"count": len(evidence), "provider": result.provider_used},
            "ts": now,
        }
    ]

    return {
        "evidence": evidence,
        "budgets": new_budgets,
        "tool_traces": traces,
        "events": events,
        "route": "analysis",
        "meta": {
            **(state.get("meta") or {}),
            "research_provider": result.provider_used,
            "research_ok": result.ok,
        },
    }
