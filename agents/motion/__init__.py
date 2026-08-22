"""Motion Agent: read-only motion-chain view from the PLC knowledge graph.

Phase 5 industrial extension — docs/industrial/05-Industrial-Agent-Design.md and
docs/architecture/ResearchOS_PLC_Intelligence.md §7. Strictly **read-only**:
this agent derives a per-axis motion view (TechnologyObject → owning Device →
blocks that write the axis) from the TIA analysis package already present in
state. It never modifies state files and never suggests writing back to a
field device.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from agents.plc.tia.graph_query import normalize_kg
from runtime.researchos_runtime.state import TaskState

#: Hard invariant — this agent must never gain a device write path.
READ_ONLY = True

#: TechnologyObject kinds that participate in a motion-chain view.
MOTION_KINDS = {"axis", "servo"}

#: Analyst finding code that flags a coil without an obvious interlock.
_NO_INTERLOCK_CODE = "OUTPUT_NO_INTERLOCK"


def _name(node_id: object) -> str:
    """``Device::PLC_1`` / ``Block::Main`` / ``Tag::Axis_1`` → short name."""
    return str(node_id).split("::", 1)[-1]


def _looks_like_kg(value: Any) -> bool:
    return isinstance(value, dict) and isinstance(value.get("nodes"), list)


def _resolve_kg(state: TaskState) -> dict[str, Any] | None:
    """Resolve the TIA analysis package's knowledge graph from state.

    The PLC agent (``agents.plc.node``) stores the KG in
    ``analysis_results["plc_tia_analysis"]["knowledge_graph"]``; a planner or
    test may also publish it as a package under ``meta["plc_tia_analysis"]`` /
    ``meta["tia_analysis"]``, or as a raw KG at ``meta["knowledge_graph"]``.
    """
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


def _collect_analyst_findings(state: TaskState) -> list[dict[str, Any]]:
    """Collect analyst findings (``agents.plc.tia.analyst``) from state if present."""
    meta = state.get("meta") or {}
    analysis_results = state.get("analysis_results") or {}

    direct = meta.get("analyst_findings")
    if isinstance(direct, list):
        return direct
    if isinstance(direct, dict) and isinstance(direct.get("findings"), list):
        return direct["findings"]

    for key in ("plc_tia_analysis", "tia_analysis"):
        pkg = meta.get(key)
        if isinstance(pkg, dict) and isinstance(pkg.get("analyst_findings"), list):
            return pkg["analyst_findings"]
    block = analysis_results.get("plc_tia_analysis")
    if isinstance(block, dict) and isinstance(block.get("analyst_findings"), list):
        return block["analyst_findings"]
    return []


def _tag_matches_axis(tag: str, axis_name: str) -> bool:
    axis = (axis_name or "").strip().lower()
    t = (tag or "").strip().lower()
    if not axis or not t:
        return False
    return t == axis or t.startswith(axis + ".") or t.startswith(axis + "[")


def _axis_writers(
    graph: dict[str, Any], axis_name: str
) -> dict[str, list[dict[str, Any]]]:
    """Block name → WRITES edges whose target tag references the axis."""
    writers: dict[str, list[dict[str, Any]]] = {}
    for edge in graph["edges"]:
        if edge.get("type") != "WRITES":
            continue
        target = str(edge.get("target") or "")
        if not target.startswith("Tag::"):
            continue
        if not _tag_matches_axis(target.removeprefix("Tag::"), axis_name):
            continue
        source = _name(edge.get("source"))
        if source:
            writers.setdefault(source, []).append(edge)
    return writers


def _device_of_to(graph: dict[str, Any], to_id: str) -> str | None:
    """Best-effort owning device via RUNS_TO (never invented)."""
    for edge in graph["edges"]:
        if edge.get("type") == "RUNS_TO" and str(edge.get("target") or "") == to_id:
            return _name(edge.get("source"))
    return None


def _finding_touches_blocks(finding: dict[str, Any], blocks: set[str]) -> bool:
    for evidence in finding.get("evidence") or []:
        if isinstance(evidence, dict) and evidence.get("block") in blocks:
            return True
    return False


def _edge_citation_id(edge: dict[str, Any]) -> str:
    return (
        f"kg:{edge.get('type')}:{edge.get('source')}->{edge.get('target')}"
    )


def _no_data(state: TaskState, now: str) -> dict[str, Any]:
    view: dict[str, Any] = {
        "axes": [],
        "status": "no_data",
        "gaps": ["no_plc_data_in_state"],
        "readonly": READ_ONLY,
    }
    return {
        "analysis_results": {
            "motion_view": {
                "specialty": "motion_view",
                "content": "## Motion View\nNo PLC/TIA analysis package found in state; nothing to derive.",
                "gaps": list(view["gaps"]),
                "citation_ids": [],
            }
        },
        "tool_traces": [
            {
                "tool": "motion.kg.view",
                "args": {},
                "result_summary": "ok=False no_plc_data",
                "ok": False,
                "duration_ms": 0,
            }
        ],
        "events": [
            {
                "type": "motion.completed",
                "task_id": state.get("task_id", ""),
                "payload": {"axes": 0, "readonly": READ_ONLY, "no_data": True},
                "ts": now,
            }
        ],
        "route": "analysis",
        "meta": {
            **(state.get("meta") or {}),
            "motion_view": view,
            "motion_readonly": READ_ONLY,
        },
    }


def run(state: TaskState) -> dict[str, Any]:
    """Motion agent entry point — deterministic, read-only KG projection."""
    started = time.monotonic()
    now = datetime.now(timezone.utc).isoformat()
    task_id = state.get("task_id", "task")

    graph = _resolve_kg(state)
    if graph is None:
        return _no_data(state, now)

    findings = _collect_analyst_findings(state)

    to_nodes = [
        node
        for node in graph["nodes"]
        if node.get("type") == "TechnologyObject"
        and ((node.get("props") or {}).get("kind") in MOTION_KINDS)
    ]

    axes: list[dict[str, Any]] = []
    for node in to_nodes:
        to_id = str(node.get("id") or "")
        props = node.get("props") if isinstance(node.get("props"), dict) else {}
        axis = str(props.get("name") or _name(to_id) or "").strip()
        device = _device_of_to(graph, to_id)
        writers = _axis_writers(graph, axis)
        writers_blocks = sorted(writers)
        writer_edges = [edge for edges in writers.values() for edge in edges]
        notes: list[str] = []
        if device is None:
            notes.append("no RUNS_TO owner device (best-effort ownership absent)")
        if not writers_blocks:
            notes.append("no WRITES edges referencing this axis tag in KG")

        writer_set = set(writers_blocks)
        interlocks = [
            finding
            for finding in findings
            if finding.get("code") == _NO_INTERLOCK_CODE
            and _finding_touches_blocks(finding, writer_set)
        ]

        axes.append(
            {
                "axis": axis,
                "kind": props.get("kind") or "",
                "to_type": props.get("to_type") or "",
                "device": device,
                "writers_blocks": writers_blocks,
                "writers": writer_edges,
                "interlocks": interlocks,
                "notes": notes,
            }
        )

    gaps: list[str] = []
    if not to_nodes:
        gaps.append("no_axis_or_servo_technology_objects")
    for axis in axes:
        if not axis["writers_blocks"]:
            gaps.append(f"no_writers_for_axis_{axis['axis']}")

    citation_ids = sorted(
        {_edge_citation_id(edge) for axis in axes for edge in axis["writers"]}
    )
    duration_ms = int((time.monotonic() - started) * 1000)

    view: dict[str, Any] = {
        "axes": axes,
        "status": "ok" if axes else "no_motion_axes",
        "gaps": gaps,
        "readonly": READ_ONLY,
    }
    lines = ["## Motion View", f"Axes analysed: {len(axes)}", ""]
    for axis in axes:
        writers = ", ".join(f"`{w}`" for w in axis["writers_blocks"]) or "(none)"
        lines.append(
            f"- Axis `{axis['axis']}` (kind={axis['kind']}, device={axis['device'] or '?'})"
            f" — writers: {writers}"
        )
    lines.append("")
    lines.append("> Read-only projection from the PLC knowledge graph; no writeback.")

    return {
        "analysis_results": {
            "motion_view": {
                "specialty": "motion_view",
                "content": "\n".join(lines),
                "gaps": gaps,
                "citation_ids": citation_ids,
            }
        },
        "tool_traces": [
            {
                "tool": "motion.kg.view",
                "args": {"axes": len(axes)},
                "result_summary": (
                    f"ok=True axes={len(axes)} "
                    f"writer_edges={len(citation_ids)}"
                ),
                "ok": True,
                "duration_ms": duration_ms,
            }
        ],
        "events": [
            {
                "type": "motion.completed",
                "task_id": task_id,
                "payload": {
                    "axes": len(axes),
                    "readonly": READ_ONLY,
                    "writers_edges": len(citation_ids),
                },
                "ts": now,
            }
        ],
        "route": "analysis",
        "meta": {
            **(state.get("meta") or {}),
            "motion_view": view,
            "motion_readonly": READ_ONLY,
        },
    }
