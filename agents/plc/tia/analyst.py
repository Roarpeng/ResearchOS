"""Evidence-gated PLC Analyst — deterministic findings from KG + folded logic.

Never invent CALLS. Every finding contains concrete KG-edge or folded-logic
evidence, so this module is safe to use without an LLM.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

try:  # Agent B may add this module independently.
    from agents.plc.tia.graph_query import (  # type: ignore[import-not-found]
        callees_of as _query_callees_of,
        callers_of as _query_callers_of,
        dead_blocks as _query_dead_blocks,
        readers_of_tag as _query_readers_of_tag,
        writers_of_tag as _query_writers_of_tag,
    )
except ImportError:  # Self-sufficient JSON KG fallbacks are used below.
    _query_callees_of = _query_callers_of = _query_dead_blocks = None
    _query_readers_of_tag = _query_writers_of_tag = None

try:
    from agents.plc.tia.flgnet_fold import stmt_to_scl as _stmt_to_scl
except ImportError:  # Folded logic is optional for older pipeline installs.
    _stmt_to_scl = None


def _name(node_id: object) -> str:
    """Turn typed KG IDs such as ``Block::Main`` into their display name."""
    return str(node_id).split("::", 1)[-1]


def _edges(job: dict[str, Any], edge_type: str | None = None) -> list[dict[str, Any]]:
    edges = (job.get("knowledge_graph") or {}).get("edges") or []
    return [
        edge
        for edge in edges
        if isinstance(edge, dict) and (edge_type is None or edge.get("type") == edge_type)
    ]


def _block_metadata(job: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {
        str(block["name"]): block
        for block in (job.get("blocks") or [])
        if isinstance(block, dict) and block.get("name")
    }
    for node in (job.get("knowledge_graph") or {}).get("nodes") or []:
        if not isinstance(node, dict) or node.get("type") != "Block":
            continue
        props = node.get("props") if isinstance(node.get("props"), dict) else {}
        name = str(props.get("name") or _name(node.get("id") or ""))
        if name:
            result.setdefault(
                name,
                {
                    "name": name,
                    "type": props.get("block_type") or props.get("type") or "",
                },
            )
    return result


def _edge_evidence(edge: dict[str, Any]) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "edge_type": str(edge.get("type") or ""),
        "source": str(edge.get("source") or ""),
        "target": str(edge.get("target") or ""),
    }
    props = edge.get("props")
    if isinstance(props, dict) and props.get("evidence"):
        evidence["source_evidence"] = props["evidence"]
    elif edge.get("evidence"):
        evidence["source_evidence"] = edge["evidence"]
    return evidence


def _call_edges(job: dict[str, Any], block_name: str, *, incoming: bool) -> list[dict[str, Any]]:
    block_id = f"Block::{block_name}"
    key = "target" if incoming else "source"
    return [edge for edge in _edges(job, "CALLS") if edge.get(key) == block_id]


def _calls(job: dict[str, Any], block_name: str) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    """Prefer optional graph-query helpers, but retain edge-level proof locally."""
    incoming = _call_edges(job, block_name, incoming=True)
    outgoing = _call_edges(job, block_name, incoming=False)
    callers = sorted({_name(edge.get("source")) for edge in incoming})
    callees = sorted({_name(edge.get("target")) for edge in outgoing})
    kg = job.get("knowledge_graph") or {}
    try:
        if _query_callers_of is not None:
            callers = sorted(set(_query_callers_of(kg, block_name)))
        if _query_callees_of is not None:
            callees = sorted(set(_query_callees_of(kg, block_name)))
    except (AttributeError, KeyError, TypeError):
        # Optional module shape is intentionally non-blocking.
        pass
    return callers, callees, [_edge_evidence(edge) for edge in incoming + outgoing]


def _io(job: dict[str, Any], block_name: str) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    block_id = f"Block::{block_name}"
    reads = [edge for edge in _edges(job, "READS") if edge.get("source") == block_id]
    writes = [edge for edge in _edges(job, "WRITES") if edge.get("source") == block_id]
    return (
        sorted({_name(edge.get("target")) for edge in reads}),
        sorted({_name(edge.get("target")) for edge in writes}),
        [_edge_evidence(edge) for edge in reads + writes],
    )


def _ob_names(job: dict[str, Any]) -> list[str]:
    return sorted(
        name
        for name, block in _block_metadata(job).items()
        if str(block.get("type") or block.get("block_type") or "").upper() == "OB"
    )


def _reachable_from_obs(job: dict[str, Any]) -> set[str]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in _edges(job, "CALLS"):
        adjacency[_name(edge.get("source"))].add(_name(edge.get("target")))
    reachable = set(_ob_names(job))
    queue: deque[str] = deque(reachable)
    while queue:
        for callee in adjacency.get(queue.popleft(), set()):
            if callee not in reachable:
                reachable.add(callee)
                queue.append(callee)
    return reachable


def _dead_block_names(job: dict[str, Any]) -> list[str]:
    blocks = _block_metadata(job)
    try:
        if _query_dead_blocks is not None:
            return sorted(set(_query_dead_blocks(job.get("knowledge_graph") or {})))
    except (AttributeError, KeyError, TypeError):
        pass
    reachable = _reachable_from_obs(job)
    return sorted(name for name in blocks if name not in reachable and name not in _ob_names(job))


def _expr_to_scl(value: Any) -> str:
    """Best-effort renderer for JSON serialized by ``folded_to_dict``."""
    if not isinstance(value, dict):
        return str(value)
    kind = value.get("type")
    if kind == "literal":
        return str(value.get("value", "(* literal *)"))
    if kind == "ref":
        return str(value.get("access", "(* ref *)"))
    if kind == "not":
        return f"NOT ({_expr_to_scl(value.get('operand'))})"
    if kind in {"and", "or"}:
        op = " AND " if kind == "and" else " OR "
        return op.join(f"({_expr_to_scl(item)})" for item in value.get("operands") or [])
    if kind == "compare":
        return f"({_expr_to_scl(value.get('lhs'))} {value.get('op', '?')} {_expr_to_scl(value.get('rhs'))})"
    return "(* folded expression unavailable *)"


def _folded_lines(job: dict[str, Any], block_name: str) -> tuple[list[str], list[dict[str, Any]]]:
    folded = (job.get("folded_logic") or {}).get(block_name) or []
    lines: list[str] = []
    evidence: list[dict[str, Any]] = []
    for network in folded:
        if not isinstance(network, dict):
            continue
        network_id = str(network.get("network_id") or "")
        for statement in network.get("statements") or []:
            if not isinstance(statement, dict):
                if _stmt_to_scl is not None:
                    lines.append(_stmt_to_scl(statement))
                    evidence.append(
                        {"kind": "folded_logic", "block": block_name, "network_id": network_id}
                    )
                continue
            target = str(statement.get("target") or "(* target unknown *)")
            condition = _expr_to_scl(statement.get("value"))
            stmt_kind = statement.get("kind")
            if stmt_kind == "neg_coil":
                line = f"{target} := NOT ({condition});"
            elif stmt_kind == "set":
                line = f"IF {condition} THEN {target} := TRUE; END_IF;"
            elif stmt_kind == "reset":
                line = f"IF {condition} THEN {target} := FALSE; END_IF;"
            else:
                line = f"{target} := {condition};"
            lines.append(line)
            evidence.append(
                {
                    "kind": "folded_logic",
                    "block": block_name,
                    "network_id": network_id,
                    "target": target,
                }
            )
    return lines, evidence


def analyze_block(job_or_ctx: dict, block_name: str) -> dict:
    """Return deterministic, evidence-carrying findings for one PLC block."""
    job = job_or_ctx
    blocks = _block_metadata(job)
    callers, callees, call_evidence = _calls(job, block_name)
    reads, writes, io_evidence = _io(job, block_name)
    folded, fold_evidence = _folded_lines(job, block_name)
    findings: list[dict[str, Any]] = []

    if call_evidence:
        findings.append(
            {
                "code": "CALL_GRAPH",
                "severity": "info",
                "message": f"`{block_name}` 的调用方: {', '.join(callers) or '无'}；调用目标: {', '.join(callees) or '无'}。",
                "evidence": call_evidence,
            }
        )
    if io_evidence:
        findings.append(
            {
                "code": "SIGNAL_FLOW",
                "severity": "info",
                "message": f"`{block_name}` 读取: {', '.join(reads) or '无'}；写入: {', '.join(writes) or '无'}。",
                "evidence": io_evidence,
            }
        )
    if folded:
        findings.append(
            {
                "code": "FOLDED_LOGIC",
                "severity": "info",
                "message": f"`{block_name}` 有 {len(folded)} 条已折叠的逻辑表达式。",
                "evidence": fold_evidence,
            }
        )

    block_type = str((blocks.get(block_name) or {}).get("type") or "").upper()
    if block_type in {"FB", "FC"} and not callers and not callees:
        findings.append(
            {
                "code": "NO_CALLS",
                "severity": "warn",
                "message": f"`{block_name}` 是 {block_type}，但 KG 中没有已验证的 CALLS 边。",
                "evidence": [
                    {
                        "kind": "block_metadata",
                        "block": block_name,
                        "block_type": block_type,
                        "calls_edges_checked": 0,
                    }
                ],
            }
        )
    if block_name in _dead_block_names(job):
        findings.append(
            {
                "code": "UNREACHABLE_FROM_OB",
                "severity": "risk",
                "message": f"`{block_name}` 未从任一 OB 入口经已验证 CALLS 边到达。",
                "evidence": [_edge_evidence(edge) for edge in _edges(job, "CALLS")] + [
                    {
                        "kind": "reachability",
                        "block": block_name,
                        "ob_entry_points": _ob_names(job),
                        "calls_edges_checked": len(_edges(job, "CALLS")),
                    }
                ],
            }
        )

    scl = (job.get("scl_sources") or {}).get(block_name)
    return {
        "block": block_name,
        "findings": findings,
        "calls": {"callers": callers, "callees": callees},
        "io": {"reads": reads, "writes": writes},
        "folded": folded,
        "scl_preview": "\n".join(str(scl).splitlines()[:40]) if scl else None,
    }


def analyze_project(job: dict) -> dict:
    """Return project-wide deterministic findings based solely on KG evidence."""
    blocks = _block_metadata(job)
    ob_entries = _ob_names(job)
    dead = _dead_block_names(job)
    call_edges = _edges(job, "CALLS")
    findings: list[dict[str, Any]] = []
    if dead:
        findings.append(
            {
                "code": "DEAD_BLOCK",
                "severity": "risk",
                "message": f"未从 OB 入口到达的块: {', '.join(dead)}。",
                "evidence": [_edge_evidence(edge) for edge in call_edges] + [
                    {
                        "kind": "reachability",
                        "ob_entry_points": ob_entries,
                        "calls_edges_checked": len(call_edges),
                        "blocks": dead,
                    }
                ],
            }
        )
    no_reads: list[str] = []
    no_writes: list[str] = []
    for name in sorted(blocks):
        reads, writes, evidence = _io(job, name)
        if not reads:
            no_reads.append(name)
        if not writes:
            no_writes.append(name)
        if evidence:
            findings.append(
                {
                    "code": "SIGNAL_FLOW",
                    "severity": "info",
                    "message": f"`{name}` 读取 {len(reads)} 个标签，写入 {len(writes)} 个标签。",
                    "evidence": evidence,
                }
            )
    return {
        "project": job.get("project_name") or "",
        "findings": findings,
        "dead_blocks": dead,
        "blocks_with_no_reads": no_reads,
        "blocks_with_no_writes": no_writes,
        "ob_entry_points": ob_entries,
        "calls_edge_count": len(call_edges),
    }


def format_analysis_markdown(result: dict) -> str:
    """Format deterministic PLC analysis as a compact Chinese chat section."""
    lines = ["## 证据门控分析", ""]
    if result.get("block"):
        lines.append(f"分析块：`{result['block']}`")
    else:
        lines.append(f"工程：`{result.get('project') or '未命名工程'}`")
        lines.append(f"- OB 入口：{', '.join(result.get('ob_entry_points') or []) or '未发现'}")
        lines.append(f"- 已验证 CALLS 边：{result.get('calls_edge_count', 0)}")
    findings = result.get("findings") or []
    if not findings:
        lines.append("- 未产生可报告的已验证发现。")
    for finding in findings:
        lines.append(f"- [{finding.get('severity', 'info')}] `{finding.get('code', 'INFO')}`：{finding.get('message', '')}")
    folded = result.get("folded") or []
    if folded:
        lines.append("")
        lines.append("已折叠逻辑：")
        for network in folded:
            for statement in (network.get("statements") or []) if isinstance(network, dict) else []:
                lines.append(f"- `{statement.get('target', '?')} := {_expr_to_scl(statement.get('value'))};`")
    lines.append("")
    lines.append("> 仅列出知识图谱边和已折叠逻辑的证据；不推断未验证的调用关系。")
    return "\n".join(lines)
