"""Failure Analysis Agent: rule-based 5-Why / FTA candidate root causes.

Phase 5 industrial extension — docs/industrial/05-Industrial-Agent-Design.md and
docs/architecture/ResearchOS_PLC_Intelligence.md §7. Strictly **read-only**:
given a symptom (``meta["failure_symptom"]`` or ``goal.raw_query``) it reverse
traces the PLC knowledge graph (symptom tag → writer blocks → upstream
READS/CALLS chains, depth ≤ 3) and emits candidate root-cause hypotheses. Every
hypothesis cites real graph edges only; when evidence is missing the gaps are
reported explicitly instead of inventing edges.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from agents.plc.tia.graph_query import normalize_kg
from runtime.researchos_runtime.state import TaskState

#: Hard invariant — this agent must never gain a device write path.
READ_ONLY = True

MAX_DEPTH = 3


def _name(node_id: object) -> str:
    return str(node_id).split("::", 1)[-1]


def _tag_name(edge: dict[str, Any]) -> str:
    target = str(edge.get("target") or "")
    if target.startswith("Tag::"):
        return target[5:]
    return ""


def _looks_like_kg(value: Any) -> bool:
    return isinstance(value, dict) and isinstance(value.get("nodes"), list)


def _resolve_kg(state: TaskState) -> dict[str, Any] | None:
    meta = state.get("meta") or {}
    analysis_results = state.get("analysis_results") or {}

    for key in ("plc_tia_analysis", "tia_analysis"):
        pkg = meta.get(key)
        if isinstance(pkg, dict) and _looks_like_kg(pkg.get("knowledge_graph")):
            return normalize_kg(pkg["knowledge_graph"])
    if _looks_like_kg(meta.get("knowledge_graph")):
        return normalize_kg(meta["knowledge_graph"])

    block = analysis_results.get("plc_tia_analysis")
    if isinstance(block, dict) and _looks_like_kg(block.get("knowledge_graph")):
        return normalize_kg(block["knowledge_graph"])
    return None


def _symptom_tag(state: TaskState, graph: dict[str, Any]) -> tuple[str, str]:
    """Return (symptom_tag, source). Prefer explicit meta, else scan the query."""
    meta = state.get("meta") or {}
    explicit = str(meta.get("failure_symptom") or "").strip().removeprefix("Tag::")
    if explicit:
        return explicit, "meta.failure_symptom"

    query = str((state.get("goal") or {}).get("raw_query") or "").lower()
    best = ""
    for node in graph["nodes"]:
        if node.get("type") != "Tag":
            continue
        props = node.get("props") if isinstance(node.get("props"), dict) else {}
        name = str(props.get("name") or _name(node.get("id")) or "").strip()
        if name and name.lower() in query and len(name) > len(best):
            best = name
    return best, "goal.raw_query"


def _confidence(depth: int) -> float:
    return round(max(0.2, 0.8 - 0.15 * (depth - 1)), 2)


def _hypothesis_text(name: str, symptom_tag: str, path: list[dict[str, Any]]) -> str:
    if not path:
        return f"块 `{name}` 为症状标签 `{symptom_tag}` 的候选根因"
    last = path[-1]
    etype = str(last.get("type") or "")
    if etype == "WRITES":
        return f"块 `{name}` 写入 `{_tag_name(last)}`（影响症状 `{symptom_tag}`）"
    if etype == "CALLS":
        return f"块 `{name}` 调用下游块（影响症状 `{symptom_tag}`）"
    if etype == "READS":
        return f"块 `{name}` 读取 `{_tag_name(last)}`（影响症状 `{symptom_tag}`）"
    return f"块 `{name}` 位于症状 `{symptom_tag}` 的上游影响链"


def _dedupe_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for edge in edges:
        key = (
            str(edge.get("source")),
            str(edge.get("target")),
            str(edge.get("type")),
            repr(edge.get("props")),
        )
        if key not in seen:
            seen.add(key)
            out.append(edge)
    return out


def _trace_candidates(
    graph: dict[str, Any], symptom_tag: str, max_depth: int = MAX_DEPTH
) -> list[dict[str, Any]]:
    """Reverse trace symptom tag → writers → upstream READS/CALLS (depth ≤ 3)."""
    writes_by_tag: dict[str, list[dict[str, Any]]] = {}
    reads_by_block: dict[str, list[dict[str, Any]]] = {}
    calls_in: dict[str, list[dict[str, Any]]] = {}

    for edge in graph["edges"]:
        etype = edge.get("type")
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if etype == "WRITES" and target.startswith("Tag::"):
            writes_by_tag.setdefault(target.removeprefix("Tag::"), []).append(edge)
        elif etype == "READS" and source.startswith("Block::"):
            reads_by_block.setdefault(source.removeprefix("Block::"), []).append(edge)
        elif etype == "CALLS" and target.startswith("Block::"):
            calls_in.setdefault(target.removeprefix("Block::"), []).append(edge)

    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = {("tag", symptom_tag)}
    # BFS queue: (kind, name, depth, path_edges)
    queue: list[tuple[str, str, int, list[dict[str, Any]]]] = [
        ("tag", symptom_tag, 0, [])
    ]

    while queue:
        kind, name, depth, path = queue.pop(0)
        if kind == "tag":
            for edge in writes_by_tag.get(name, []):
                writer = _name(edge.get("source"))
                next_depth = depth + 1
                if not writer or next_depth > max_depth:
                    continue
                key = ("block", writer)
                if key in seen:
                    continue
                seen.add(key)
                new_path = path + [edge]
                candidates.append(
                    {
                        "hypothesis": _hypothesis_text(writer, symptom_tag, new_path),
                        "node": {"kind": "block", "name": writer},
                        "depth": next_depth,
                        "confidence": _confidence(next_depth),
                        "supporting_edges": list(new_path),
                    }
                )
                queue.append(("block", writer, next_depth, new_path))
        else:  # block
            # Upstream callers (who CALLS this block)
            for edge in calls_in.get(name, []):
                caller = _name(edge.get("source"))
                next_depth = depth + 1
                if not caller or next_depth > max_depth:
                    continue
                key = ("block", caller)
                if key in seen:
                    continue
                seen.add(key)
                new_path = path + [edge]
                candidates.append(
                    {
                        "hypothesis": _hypothesis_text(caller, symptom_tag, new_path),
                        "node": {"kind": "block", "name": caller},
                        "depth": next_depth,
                        "confidence": _confidence(next_depth),
                        "supporting_edges": list(new_path),
                    }
                )
                queue.append(("block", caller, next_depth, new_path))

            # Upstream reads: this block reads tag T → who writes T
            for read_edge in reads_by_block.get(name, []):
                tag = _tag_name(read_edge)
                if not tag:
                    continue
                for write_edge in writes_by_tag.get(tag, []):
                    upstream = _name(write_edge.get("source"))
                    next_depth = depth + 2
                    if not upstream or next_depth > max_depth:
                        continue
                    key = ("block", upstream)
                    if key in seen:
                        continue
                    seen.add(key)
                    new_path = path + [read_edge, write_edge]
                    candidates.append(
                        {
                            "hypothesis": _hypothesis_text(upstream, symptom_tag, new_path),
                            "node": {"kind": "block", "name": upstream},
                            "depth": next_depth,
                            "confidence": _confidence(next_depth),
                            "supporting_edges": list(new_path),
                        }
                    )
                    queue.append(("block", upstream, next_depth, new_path))

    return candidates


def _no_data(state: TaskState, now: str) -> dict[str, Any]:
    analysis: dict[str, Any] = {
        "symptom": None,
        "symptom_source": None,
        "candidates": [],
        "evidence": [],
        "gaps": ["no_plc_data_in_state"],
        "readonly": READ_ONLY,
        "status": "no_data",
    }
    return {
        "analysis_results": {
            "failure_analysis": {
                "specialty": "failure_analysis",
                "content": "## Failure Analysis\nNo PLC/TIA analysis package found in state.",
                "gaps": list(analysis["gaps"]),
                "citation_ids": [],
            }
        },
        "tool_traces": [
            {
                "tool": "failure.kg.trace",
                "args": {},
                "result_summary": "ok=False no_plc_data",
                "ok": False,
                "duration_ms": 0,
            }
        ],
        "events": [
            {
                "type": "failure.completed",
                "task_id": state.get("task_id", ""),
                "payload": {"candidates": 0, "readonly": READ_ONLY, "no_data": True},
                "ts": now,
            }
        ],
        "route": "analysis",
        "meta": {
            **(state.get("meta") or {}),
            "failure_analysis": analysis,
            "failure_readonly": READ_ONLY,
        },
    }


def run(state: TaskState) -> dict[str, Any]:
    """Failure analysis entry point — deterministic, read-only KG trace."""
    started = time.monotonic()
    now = datetime.now(timezone.utc).isoformat()
    task_id = state.get("task_id", "task")

    graph = _resolve_kg(state)
    if graph is None:
        return _no_data(state, now)

    symptom_tag, symptom_source = _symptom_tag(state, graph)
    gaps: list[str] = []
    if not symptom_tag:
        gaps.append("no_failure_symptom")

    candidates = (
        _trace_candidates(graph, symptom_tag) if symptom_tag else []
    )
    evidence = _dedupe_edges(
        [edge for cand in candidates for edge in cand["supporting_edges"]]
    )
    citation_ids = sorted(
        {
            f"kg:{edge.get('type')}:{edge.get('source')}->{edge.get('target')}"
            for edge in evidence
        }
    )

    if symptom_tag and not candidates:
        gaps.append(f"no_writers_for_symptom_tag_{symptom_tag}")

    analysis: dict[str, Any] = {
        "symptom": symptom_tag or None,
        "symptom_source": symptom_source if symptom_tag else None,
        "candidates": candidates,
        "evidence": evidence,
        "gaps": gaps,
        "readonly": READ_ONLY,
        "status": "ok" if candidates else "no_candidates",
    }
    duration_ms = int((time.monotonic() - started) * 1000)

    lines = ["## Failure Analysis (5-Why / FTA candidates)", ""]
    if symptom_tag:
        lines.append(f"Symptom tag: `{symptom_tag}` (from {symptom_source})")
    lines.append("")
    for cand in candidates:
        node = cand["node"]
        lines.append(
            f"- [{cand['confidence']}] `{node['name']}` (depth {cand['depth']}) — "
            f"{cand['hypothesis']}"
        )
    if not candidates:
        lines.append("- No candidate root causes could be traced from KG evidence.")
    if gaps:
        lines.append("")
        lines.append("Gaps: " + ", ".join(f"`{g}`" for g in gaps))
    lines.append("")
    lines.append("> Every hypothesis cites real KG edges only; nothing is invented.")

    return {
        "analysis_results": {
            "failure_analysis": {
                "specialty": "failure_analysis",
                "content": "\n".join(lines),
                "gaps": gaps,
                "citation_ids": citation_ids,
            }
        },
        "tool_traces": [
            {
                "tool": "failure.kg.trace",
                "args": {"symptom": symptom_tag or "", "max_depth": MAX_DEPTH},
                "result_summary": (
                    f"ok=True candidates={len(candidates)} "
                    f"evidence_edges={len(evidence)}"
                ),
                "ok": True,
                "duration_ms": duration_ms,
            }
        ],
        "events": [
            {
                "type": "failure.completed",
                "task_id": task_id,
                "payload": {
                    "symptom": symptom_tag,
                    "candidates": len(candidates),
                    "evidence_edges": len(evidence),
                    "readonly": READ_ONLY,
                },
                "ts": now,
            }
        ],
        "route": "analysis",
        "meta": {
            **(state.get("meta") or {}),
            "failure_analysis": analysis,
            "failure_readonly": READ_ONLY,
        },
    }
