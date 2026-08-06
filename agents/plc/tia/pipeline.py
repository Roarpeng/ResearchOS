"""TIA -> SCL pipeline orchestration.

TIA Project -> Openness (export) -> Extract (SimaticML parse) -> PLC-IR
-> Knowledge Graph + SCL translation -> interpretation report for the
LLM Agent / engineer review.
"""

from __future__ import annotations

from typing import Any

from agents.plc.tia.ir import BlockType, PlcProject
from agents.plc.tia.kg import PlcKnowledgeGraph, build_knowledge_graph
from agents.plc.tia.scl import convert_project_to_scl
from agents.plc.tia.simaticml import extract_project


def analyze_tia_exports(export_dir: str, *, project_name: str = "") -> dict[str, Any]:
    """Full pipeline: parse Openness exports, build KG, convert to SCL."""
    project = extract_project(export_dir, project_name=project_name)
    kg = build_knowledge_graph(project)
    scl_sources = convert_project_to_scl(project)
    return {
        "project": project,
        "knowledge_graph": kg,
        "scl_sources": scl_sources,
        "report": interpretation_report(project, kg),
    }


def interpretation_report(project: PlcProject, kg: PlcKnowledgeGraph) -> str:
    """Human/LLM-readable summary explaining the parsed project."""
    lines: list[str] = []
    lines.append(f"# TIA Project Interpretation: {project.name}")
    lines.append("")

    summary = project.summary()
    lines.append("## Overview")
    lines.append(
        f"- Blocks: {summary.get('FB', 0)} FB / {summary.get('FC', 0)} FC / "
        f"{summary.get('OB', 0)} OB / {summary.get('DB', 0)} DB / {summary.get('UDT', 0)} UDT"
    )
    lines.append(f"- Tag tables: {summary.get('TagTables', 0)}, Networks: {summary.get('Networks', 0)}")
    if project.extraction_notes:
        lines.append("- Extraction notes:")
        lines.extend(f"  - {note}" for note in project.extraction_notes)
    lines.append("")

    lines.append("## Blocks")
    for block in project.blocks.values():
        title = f"- **{block.block_type.value} {block.name}**"
        if block.number:
            title += f" ({block.block_type.value}{block.number})"
        if block.programming_language:
            title += f" [{block.programming_language}]"
        if block.header_comment:
            title += f" — {block.header_comment}"
        lines.append(title)
        callees = kg.callees_of(block.name)
        if callees:
            lines.append(f"  - Calls: {', '.join(callees)}")
        if block.block_type == BlockType.FB:
            instances = sorted(
                e.source.split("::")[1]
                for e in kg.in_edges(f"Block::{block.name}", "INSTANCE_OF")
            )
            if instances:
                lines.append(f"  - Instances: {', '.join(instances)}")
    lines.append("")

    # IO summary
    tag_reads: dict[str, set[str]] = {}
    tag_writes: dict[str, set[str]] = {}
    for edge in kg.edges:
        if edge.type == "READS" and edge.target.startswith("Tag::"):
            tag_reads.setdefault(edge.target[5:], set()).add(edge.source.split("::")[1])
        elif edge.type == "WRITES" and edge.target.startswith("Tag::"):
            tag_writes.setdefault(edge.target[5:], set()).add(edge.source.split("::")[1])
    if tag_reads or tag_writes:
        lines.append("## Signal Flow (tag read/write by block)")
        for ref in sorted(set(tag_reads) | set(tag_writes)):
            readers = sorted(tag_reads.get(ref, set()))
            writers = sorted(tag_writes.get(ref, set()))
            lines.append(f"- `{ref}` — read by {', '.join(readers) or '-'}; written by {', '.join(writers) or '-'}")
        lines.append("")

    lines.append("## Safety Notes")
    lines.append("- Output is advisory SCL; review before importing to TIA Portal.")
    lines.append("- Import path: External Source (.scl) -> GenerateBlocksFromSource().")
    lines.append("- Untranslated instructions are marked with `(* TODO[...] *)` comments.")
    return "\n".join(lines)
