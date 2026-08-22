"""Research Agent node: SearchRouter → evidence[] (+ optional crawl stub)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from runtime.researchos_runtime.state import Budgets, TaskState
from tools.browser.crawl import fetch as crawl_fetch
from tools.search_router.router import SearchBudget, SearchRouter


def _budgets(state: TaskState) -> Budgets:
    return dict(state.get("budgets") or {})  # type: ignore[return-value]


def _search_round(
    state: TaskState,
    query: str,
    *,
    limit: int,
    ev_counter: int,
    is_followup: bool,
    followup_specialty: str | None,
    now: str,
) -> dict[str, Any]:
    """Run one search query and build evidence for its hits."""
    router = SearchRouter(
        budget=SearchBudget(max_queries=1, used_queries=0, max_fetches=1)
    )
    result = router.query(query, limit=limit, provider="auto")

    evidence: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
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

    used_delta = 1
    for idx, hit in enumerate(result.results, start=1):
        eid = f"ev_{state.get('task_id', 'task')}_{ev_counter + idx}"
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
            used_delta += 1

        meta: dict[str, Any] = {
            "retrieved_at": now,
            "retrieved_by": "research",
            "provider": hit.raw_provider,
            "source_type": hit.source_type,
            "hit_id": hit.id,
        }
        if is_followup:
            meta["followup"] = True
            if followup_specialty:
                meta["followup_specialty"] = followup_specialty

        evidence.append(
            {
                "id": eid,
                "source_id": hit.source_id or hit.url or hit.id,
                "title": hit.title,
                "content": content,
                "url": hit.url or "",
                "locator": hit.id,
                "score": hit.score,
                "meta": meta,
            }
        )

    return {
        "evidence": evidence,
        "traces": traces,
        "used_delta": used_delta,
        "next_ev_counter": ev_counter + len(result.results),
        "provider_used": result.provider_used,
        "ok": result.ok,
    }


def run(state: TaskState) -> dict[str, Any]:
    goal = state.get("goal") or {}
    main_query = (
        goal.get("normalized_objective")
        or goal.get("raw_query")
        or "research topic"
    )
    budgets = _budgets(state)
    max_tool = int(budgets.get("max_tool_calls") or 40)
    used_tool = int(budgets.get("used_tool_calls") or 0)
    remaining = max(0, max_tool - used_tool)

    meta = dict(state.get("meta") or {})
    followups = list(meta.get("review_followups") or [])

    # Follow-ups first (targeted re-search), then the main query.
    query_plan: list[tuple[str, str | None]] = []
    for followup in followups:
        if isinstance(followup, dict):
            query = str(followup.get("query") or "").strip()
            specialty = followup.get("specialty")
        else:
            query = str(followup).strip()
            specialty = None
        if query:
            query_plan.append((query, specialty))
    query_plan.append((main_query, None))

    evidence: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()
    ev_counter = 0
    used_delta = 0
    last_provider = "none"
    last_ok = False

    for query, followup_specialty in query_plan:
        limit = min(5, remaining or 1)
        round_out = _search_round(
            state,
            query,
            limit=limit,
            ev_counter=ev_counter,
            is_followup=followup_specialty is not None,
            followup_specialty=followup_specialty,
            now=now,
        )
        evidence.extend(round_out["evidence"])
        traces.extend(round_out["traces"])
        ev_counter = int(round_out["next_ev_counter"])
        used_delta += int(round_out["used_delta"])
        remaining = max(0, remaining - int(round_out["used_delta"]))
        last_provider = round_out["provider_used"]
        last_ok = bool(round_out["ok"])

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
            "payload": {
                "count": len(evidence),
                "provider": last_provider,
                "followup_rounds": max(0, len(query_plan) - 1),
            },
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
            **meta,
            "review_followups": [],  # consume follow-ups so they are not re-run
            "research_provider": last_provider,
            "research_ok": last_ok,
        },
    }
