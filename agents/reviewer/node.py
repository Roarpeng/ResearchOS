"""Reviewer Agent node: citation coverage + contradiction + criteria gate."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from runtime.researchos_runtime.state import TaskState

CLAIMISH = re.compile(
    r"(建议|结论|风险|份额|价格|认证|IP\d+|ISO\s*\d+|推荐|competitors?|risk)",
    re.IGNORECASE,
)

# --- Contradiction heuristics -------------------------------------------------

# number + optional unit (%, kg, mm, 家, 元, ...). Unit is required to count.
NUMBER_RE = re.compile(
    r"(?P<num>[0-9]+(?:\.[0-9]+)?)\s*"
    r"(?P<unit>%|％|percent|percentage|kg|公斤|g|克|mm|毫米|cm|厘米|m|米|km|千米|"
    r"s|秒|ms|毫秒|hz|khz|mhz|ghz|w|kw|v|a|n|nm|°c|℃|db|分贝|"
    r"个|家|元|人民币|美元|usd|eur|rmb|倍)",
    re.IGNORECASE,
)

# IP rating (IP67 vs IP65 …) treated as its own dimension.
IP_RE = re.compile(r"\bip\s*(?P<num>[0-9]{1,2})\b", re.IGNORECASE)

# Polarity synonym groups. Oppose terms are matched and masked first so that
# "不支持" does not also fire the "支持" support rule.
OPPOSE_WORDS = (
    "不支持",
    "反对",
    "不可行",
    "不建议",
    "不推荐",
    "not support",
    "not feasible",
    "not viable",
    "not recommended",
    "infeasible",
    "unviable",
    "disagree",
    "disagrees",
)
SUPPORT_WORDS = (
    "支持",
    "可行",
    "赞成",
    "推荐",
    "同意",
    "support",
    "supports",
    "supported",
    "feasible",
    "viable",
    "recommend",
    "recommended",
    "agree",
    "agrees",
)

_OPPOSE_RE = re.compile(
    "|".join(re.escape(w) for w in sorted(OPPOSE_WORDS, key=len, reverse=True)),
    re.IGNORECASE,
)
_SUPPORT_RE = re.compile(
    "|".join(re.escape(w) for w in sorted(SUPPORT_WORDS, key=len, reverse=True)),
    re.IGNORECASE,
)


def _subject_of(text: str, index: int) -> str:
    """Rough topic key from the tokens immediately preceding a match."""
    before = text[max(0, index - 24):index].lower()
    toks = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", before)
    toks = [t for t in toks if not t.isdigit()][-4:]
    subject = " ".join(toks).strip()
    return subject or "general"


def _extract_assertions(
    text: str,
    *,
    source: str,
    evidence_ids: list[str],
) -> list[dict[str, Any]]:
    text = text or ""
    out: list[dict[str, Any]] = []

    for m in IP_RE.finditer(text):
        out.append(
            {
                "kind": "numeric",
                "dimension": "ip",
                "value": float(m.group("num")),
                "raw": m.group(0),
                "subject": _subject_of(text, m.start()),
                "source": source,
                "evidence_ids": list(evidence_ids),
            }
        )

    for m in NUMBER_RE.finditer(text):
        unit = (m.group("unit") or "").strip().lower()
        if not unit:
            continue
        out.append(
            {
                "kind": "numeric",
                "dimension": unit,
                "value": float(m.group("num")),
                "raw": m.group(0),
                "subject": _subject_of(text, m.start()),
                "source": source,
                "evidence_ids": list(evidence_ids),
            }
        )

    # polarity — oppose first, then mask those spans before matching support
    for m in _OPPOSE_RE.finditer(text):
        out.append(
            {
                "kind": "polarity",
                "polarity": -1,
                "raw": m.group(0),
                "subject": _subject_of(text, m.start()),
                "source": source,
                "evidence_ids": list(evidence_ids),
            }
        )
    masked = _OPPOSE_RE.sub(lambda m: " " * len(m.group(0)), text)
    for m in _SUPPORT_RE.finditer(masked):
        out.append(
            {
                "kind": "polarity",
                "polarity": 1,
                "raw": m.group(0),
                "subject": _subject_of(text, m.start()),
                "source": source,
                "evidence_ids": list(evidence_ids),
            }
        )

    return out


def _detect_contradictions(assertions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    numeric: dict[tuple[str, str], list[dict[str, Any]]] = {}
    polarity: dict[str, list[dict[str, Any]]] = {}

    for a in assertions:
        if a["kind"] == "numeric":
            numeric.setdefault((a["subject"], a["dimension"]), []).append(a)
        else:
            polarity.setdefault(a["subject"], []).append(a)

    reasons: list[dict[str, Any]] = []

    for (subject, dimension), items in numeric.items():
        by_value: dict[float, list[dict[str, Any]]] = {}
        for a in items:
            by_value.setdefault(a["value"], []).append(a)
        if len(by_value) < 2:
            continue
        eids = list(dict.fromkeys(e for a in items for e in a["evidence_ids"] if e))
        if len(eids) < 2:
            continue
        reasons.append(
            {
                "kind": "contradiction",
                "topic": f"{subject}:{dimension}",
                "message": f"conflicting numeric assertions for {subject} [{dimension}]",
                "assertions": [
                    {"value": a["raw"], "source": a["source"]} for a in items
                ][:8],
                "evidence_ids": eids,
            }
        )

    for subject, items in polarity.items():
        pos = [a for a in items if a["polarity"] > 0]
        neg = [a for a in items if a["polarity"] < 0]
        if not pos or not neg:
            continue
        eids = list(dict.fromkeys(e for a in items for e in a["evidence_ids"] if e))
        if len(eids) < 2:
            continue
        reasons.append(
            {
                "kind": "contradiction",
                "topic": subject,
                "message": f"conflicting polarity assertions for {subject}",
                "assertions": [
                    {"polarity": a["polarity"], "raw": a["raw"], "source": a["source"]}
                    for a in items
                ][:8],
                "evidence_ids": eids,
            }
        )

    return reasons


# --- success_criteria heuristic ---------------------------------------------


def _tokens(text: str) -> set[str]:
    text = (text or "").lower()
    latin = set(re.findall(r"[a-z][a-z0-9]{2,}", text))
    bigrams: set[str] = set()
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        for i in range(len(run) - 1):
            bigrams.add(run[i:i + 2])
    return latin | bigrams


def _criterion_hit(criterion: str, content: str) -> bool:
    crit_tokens = _tokens(criterion)
    if not crit_tokens:
        return True
    overlap = len(crit_tokens & _tokens(content))
    return overlap >= max(1, len(crit_tokens) // 2)


# --- gap → followup mapping ---------------------------------------------------


def _build_followups(
    gaps: list[str],
    contradictions: list[dict[str, Any]],
    *,
    main_query: str,
) -> list[dict[str, Any]]:
    followups: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(specialty: str, query: str, priority: int) -> None:
        q = (query or "").strip()
        if not q:
            return
        key = (specialty, q)
        if key in seen:
            return
        seen.add(key)
        followups.append({"specialty": specialty, "query": q, "priority": priority})

    for gap in gaps:
        if gap == "missing_evidence":
            add("research", main_query, 1)
        elif gap == "missing_citations":
            add("research", main_query, 2)
        elif gap.startswith("success_criteria_unmet::"):
            add("research", gap.split("::", 1)[1], 2)

    for contra in contradictions:
        topic = str(contra.get("topic") or "").strip()
        query = f"{main_query} {topic}".strip() if topic else main_query
        add("research", query, 1)

    followups.sort(key=lambda f: int(f.get("priority") or 3))
    return followups


def run(state: TaskState) -> dict[str, Any]:
    evidence = list(state.get("evidence") or [])
    citations = list(state.get("citations") or [])
    analysis = dict(state.get("analysis_results") or {})
    result_md = state.get("result")
    goal = state.get("goal") or {}
    main_query = (
        goal.get("normalized_objective") or goal.get("raw_query") or "research topic"
    )

    citation_ids = {str(c.get("id")) for c in citations if c.get("id")}
    citation_to_evidence = {
        str(c.get("id")): c.get("evidence_id") for c in citations if c.get("id")
    }
    reasons: list[Any] = []
    gaps: list[str] = []
    citation_issues: list[str] = []

    if not evidence:
        reasons.append("evidence is empty")
        gaps.append("missing_evidence")

    if not citations:
        reasons.append("citations are empty")
        gaps.append("missing_citations")
        citation_issues.append("no citations present")

    for specialty, block in analysis.items():
        block = block or {}
        content = str(block.get("content") or "")
        cite_ids = [str(x) for x in (block.get("citation_ids") or [])]
        looks_like_claim = bool(CLAIMISH.search(content)) or len(content) > 40

        if looks_like_claim and not cite_ids:
            reasons.append(f"analysis.{specialty} lacks citation_ids")
            gaps.append("missing_citations")
            citation_issues.append(f"analysis_results.{specialty}")
            continue

        for cid in cite_ids:
            if cid.startswith("TMP:"):
                citation_issues.append(f"{specialty}:{cid} not normalized")
                reasons.append(f"unnormalized citation ref in {specialty}")
                gaps.append("invalid_citation_id")
            elif cid not in citation_ids:
                citation_issues.append(f"{specialty}:{cid} missing from citations[]")
                reasons.append(f"unknown citation id {cid} in {specialty}")
                gaps.append("invalid_citation_id")

    if result_md:
        markers = re.findall(r"\[\^([^\]]+)\]|\[citation:([^\]]+)\]|\(\[(C\d+)\]\)", result_md)
        flat = [m for group in markers for m in group if m]
        for mid in flat:
            if mid not in citation_ids:
                citation_issues.append(f"result marker {mid} unresolved")
                gaps.append("invalid_citation_id")
                reasons.append(f"unresolved marker {mid} in result")

    # 1. Contradiction detection across evidence and analysis
    assertions: list[dict[str, Any]] = []
    for item in evidence:
        eid = str(item.get("id") or "")
        text = str(item.get("content") or "")
        assertions.extend(
            _extract_assertions(
                text,
                source=f"evidence:{eid}",
                evidence_ids=[eid] if eid else [],
            )
        )
    for specialty, block in analysis.items():
        block = block or {}
        cite_ids = [str(x) for x in (block.get("citation_ids") or [])]
        ev_ids = [citation_to_evidence.get(cid, cid) for cid in cite_ids]
        assertions.extend(
            _extract_assertions(
                str(block.get("content") or ""),
                source=f"analysis:{specialty}",
                evidence_ids=[e for e in ev_ids if e],
            )
        )

    contradictions = _detect_contradictions(assertions)
    for contra in contradictions:
        reasons.append(contra)
        gaps.append("contradiction")

    # 2. success_criteria coverage
    criteria = [str(c) for c in (goal.get("success_criteria") or [])]
    content_blob = " ".join(
        [result_md or ""]
        + [str((b or {}).get("content") or "") for b in analysis.values()]
    )
    for crit in criteria:
        if not _criterion_hit(crit, content_blob):
            reasons.append(f"success criterion unmet: {crit}")
            gaps.append(f"success_criteria_unmet::{crit}")

    verdict = "pass" if not reasons else "reject"
    review = {
        "verdict": verdict,
        "reasons": reasons,
        "gaps": list(dict.fromkeys(gaps)),
        "citation_issues": citation_issues,
    }

    # 3. Directed follow-ups for the next research round
    followups = _build_followups(review["gaps"], contradictions, main_query=main_query)

    now = datetime.now(timezone.utc).isoformat()
    return {
        "review": review,
        "route": "writer" if verdict == "pass" else "research",
        "meta": {
            **(state.get("meta") or {}),
            "review_followups": followups,
        },
        "events": [
            {
                "type": "review.completed",
                "task_id": state.get("task_id", ""),
                "payload": {
                    "verdict": verdict,
                    "gaps": review["gaps"],
                    "contradictions": len(contradictions),
                    "followups": len(followups),
                },
                "ts": now,
            }
        ],
    }
