r"""CLI entry point for the TIA -> SCL offline pipeline.

Usage (matches the hint printed by industrial/tia_adapter/ExportProject.ps1):

    researchos-tia-cli --exports C:\Export\Line1 --out .\scl_out --kg kg.json
    python -m agents.plc.tia_cli --exports ./exports --out ./scl_out --kg kg.json

Read-only by design: parses Openness SimaticML exports, builds the
knowledge graph, prints an interpretation report and (optionally)
writes generated .scl sources for engineer review.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from agents.plc.tia import analyze_tia_exports


def _safe_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="researchos-tia-cli",
        description="Analyze TIA Portal Openness exports (SimaticML XML) and "
        "convert the project to SCL (read-only).",
    )
    parser.add_argument(
        "--exports", required=True, help="Directory with SimaticML XML exports"
    )
    parser.add_argument("--project-name", default="", help="Display name for the project")
    parser.add_argument(
        "--out", default="", help="Directory to write generated .scl files (optional)"
    )
    parser.add_argument(
        "--kg", default="", help="Path to write the knowledge graph JSON (optional)"
    )
    parser.add_argument(
        "--json-summary",
        action="store_true",
        help="Print a machine-readable summary line after the report",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Exit 0 even when no blocks were recognized (default: non-zero)",
    )
    args = parser.parse_args(argv)

    export_path = Path(args.exports).expanduser()
    if not export_path.is_dir():
        print(f"error: export directory not found: {export_path}", file=sys.stderr)
        return 2

    result = analyze_tia_exports(str(export_path), project_name=args.project_name)
    project = result["project"]
    kg = result["knowledge_graph"]
    scl_sources: dict[str, str] = result["scl_sources"]
    summary = project.summary()

    print(result["report"])
    print()
    print("## Extraction stats")
    print(
        f"- XML scanned under: `{export_path}`\n"
        f"- Blocks: {len(project.blocks)} | Tag tables: {len(project.tag_tables)} | "
        f"SCL sources: {len(scl_sources)} | KG nodes: {len(kg.nodes)} | "
        f"KG edges: {len(kg.edges)}"
    )
    print()
    for name, source in scl_sources.items():
        print(f"{'=' * 72}\n-- SCL: {name}\n{'=' * 72}")
        print(source)

    if args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, source in scl_sources.items():
            target = out_dir / f"{_safe_filename(name)}.scl"
            target.write_text(source, encoding="utf-8")
            print(f"wrote {target}")

    if args.kg:
        kg_path = Path(args.kg)
        kg_path.parent.mkdir(parents=True, exist_ok=True)
        kg_path.write_text(
            json.dumps(kg.to_json(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"wrote {kg_path}")

    if project.extraction_notes:
        print("\nExtraction notes:", file=sys.stderr)
        for note in project.extraction_notes:
            print(f"  - {note}", file=sys.stderr)

    payload = {
        "ok": bool(project.blocks),
        "export_dir": str(export_path),
        "project_name": project.name,
        "blocks": len(project.blocks),
        "tag_tables": len(project.tag_tables),
        "scl_sources": len(scl_sources),
        "kg_nodes": len(kg.nodes),
        "kg_edges": len(kg.edges),
        "summary": summary,
        "notes": list(project.extraction_notes),
    }
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))

    if not project.blocks and not args.allow_empty:
        print(
            "error: no PLC blocks recognized. Re-export with "
            "industrial/tia_adapter/ExportProject.ps1 or pass --allow-empty.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
