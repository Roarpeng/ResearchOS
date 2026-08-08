"""mcp-plc server — read-only PLC manual tools (Phase 5 industrial).

Aligned with docs/industrial/02-plc-and-automation.md:

- `plc.manual.search` / `plc.manual.get` / `plc.vendors.list` — open
- `plc.alarm.explain` — open; every explanation carries a manual citation
- `plc.program.download` — disabled by default (high risk, never on)
- `plc.program.upload_suggest` — disabled unless explicitly flagged

The server depends on the `PlcDocsConnector` protocol, not a vendor SDK.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from industrial.connectors.plc_docs import FakePlcDocsConnector
from tools._mcp_compat import create_mcp_server

mcp = create_mcp_server("plc")

_connector = FakePlcDocsConnector()

#: Sample alarm knowledge base — explanations must always cite a manual.
ALARM_CATALOG: dict[str, dict[str, Any]] = {
    "E2304": {
        "description": "Packaging line servo drive communication fault",
        "candidates": [
            "PROFINET/EtherNet/IP link instability on the drive segment",
            "Drive firmware mismatch with controller configuration",
            "Cable/shielding degradation near high-power lines",
        ],
        "manual_ref": "plc_siemens_s7",
    },
    "F0002": {
        "description": "DC bus overvoltage",
        "candidates": [
            "Regenerative energy without braking resistor",
            "Deceleration ramp too short for load inertia",
        ],
        "manual_ref": "plc_beck_compactlogix",
    },
}


def _flag_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


@mcp.tool(name="plc.vendors.list")
def plc_vendors_list() -> dict[str, Any]:
    """List PLC manual vendors available in the connected catalog."""
    return {"ok": True, "readonly": True, "vendors": _connector.list_vendors()}


@mcp.tool(name="plc.manual.search")
def plc_manual_search(query: str, limit: int = 10) -> dict[str, Any]:
    """Search ingested PLC manuals (read-only)."""
    hits = _connector.search(query, limit=limit)
    return {
        "ok": True,
        "readonly": True,
        "count": len(hits),
        "results": [_connector.as_dict(e) for e in hits],
    }


@mcp.tool(name="plc.manual.get")
def plc_manual_get(doc_id: str) -> dict[str, Any]:
    """Fetch one PLC manual entry by id (read-only)."""
    entry = _connector.get(doc_id)
    if entry is None:
        return {"ok": False, "error": "not_found", "doc_id": doc_id}
    return {"ok": True, "readonly": True, "document": _connector.as_dict(entry)}


@mcp.tool(name="plc.alarm.explain")
def plc_alarm_explain(alarm_code: str) -> dict[str, Any]:
    """Explain an alarm code with candidate causes; citations required."""
    code = (alarm_code or "").strip().upper()
    info = ALARM_CATALOG.get(code)
    if info is None:
        return {
            "ok": False,
            "error": "unknown_alarm_code",
            "alarm_code": code,
            "hint": "No curated explanation; retrieve manuals via plc.manual.search.",
        }
    manual = _connector.get(info["manual_ref"])
    citation = _connector.as_dict(manual) if manual else None
    return {
        "ok": True,
        "readonly": True,
        "alarm_code": code,
        "description": info["description"],
        "candidate_causes": info["candidates"],
        "citation": citation,
        "disclaimer": "Advisory only; follow enterprise change management (MOC).",
    }


@mcp.tool(name="plc.tia.analyze")
def plc_tia_analyze(
    export_dir: str,
    project_name: str = "",
    publish_graph: bool = False,
) -> dict[str, Any]:
    """Analyze a TIA Portal Openness export folder -> KG + SCL (read-only).

    `export_dir` must contain SimaticML XML produced by Openness
    `PlcBlock.Export(...)` (see industrial/tia_adapter or tia-openness MCP).
    Returns the interpretation report, generated SCL sources and the
    knowledge graph; never writes to any TIA project.
    Set `publish_graph=true` to upsert PLC nodes into Neo4j/memory KG.
    """
    export_path = Path(export_dir).expanduser()
    if not export_path.is_dir():
        return {
            "ok": False,
            "error": "export_dir_not_found",
            "export_dir": str(export_dir),
        }
    from agents.plc.tia import analyze_tia_exports

    result = analyze_tia_exports(
        str(export_path),
        project_name=project_name,
        publish_graph=publish_graph,
    )
    project = result["project"]
    payload: dict[str, Any] = {
        "ok": True,
        "readonly": True,
        "project_name": project.name,
        "summary": project.summary(),
        "extraction_notes": project.extraction_notes,
        "report": result["report"],
        "scl_sources": result["scl_sources"],
        "knowledge_graph": result["knowledge_graph"].to_json(),
        "conversion_report": result.get("conversion_report"),
    }
    if "graph_publish" in result:
        payload["graph_publish"] = result["graph_publish"]
    return payload


@mcp.tool(name="plc.tia.ingest")
def plc_tia_ingest(
    path: str,
    project_name: str = "",
    result_dir: str = "",
    publish_graph: bool = True,
    tia_version: str = "",
    plc_name: str = "",
) -> dict[str, Any]:
    """Bridge: XML | .apxx | export dir → Parser → PLC-IR → KG → (Neo4j) → Agent payload.

    Preferred Milestone-1 follow-on tool after `tia.export_block` / `tia.export_project`.
    """
    target = Path(path).expanduser()
    if not target.exists():
        return {"ok": False, "error": "path_not_found", "path": str(path)}
    from agents.plc.tia import analyze_plc_project

    try:
        result = analyze_plc_project(
            str(target),
            project_name=project_name,
            result_dir=result_dir,
            tia_version=tia_version,
            plc_name=plc_name,
            publish_graph=publish_graph,
        )
    except FileNotFoundError as exc:
        return {"ok": False, "error": "not_found", "message": str(exc)}
    except (RuntimeError, ValueError) as exc:
        return {"ok": False, "error": "ingest_failed", "message": str(exc)}

    project = result["project"]
    return {
        "ok": True,
        "readonly": True,
        "pipeline": "XML→PLC-IR→KG→Neo4j→Agent",
        "project_name": project.name,
        "import": result.get("import"),
        "result_dir": result.get("result_dir") or "",
        "summary": project.summary(),
        "conversion_report": result.get("conversion_report"),
        "report": result["report"],
        "scl_sources": result["scl_sources"],
        "knowledge_graph": result["knowledge_graph"].to_json(),
        "graph_publish": result.get("graph_publish"),
        "extraction_notes": project.extraction_notes,
    }


@mcp.tool(name="plc.project.analyze")
def plc_project_analyze(
    path: str,
    result_dir: str = "",
    project_name: str = "",
    tia_version: str = "",
    plc_name: str = "",
    export_dir: str = "",
    publish_graph: bool = False,
) -> dict[str, Any]:
    """One-shot Offline Analyzer: .apxx or export folder -> SCL result package.

    For `.ap17`/`.ap18`/`.ap19`/`.ap20`, runs Openness export then offline
    parse/understand/convert. For an export directory, skips Openness.
    Optionally writes `ResearchOS_PLC_Result` layout under `result_dir`.
    """
    target = Path(path).expanduser()
    if not target.exists():
        return {"ok": False, "error": "path_not_found", "path": str(path)}
    from agents.plc.tia import analyze_plc_project

    try:
        result = analyze_plc_project(
            str(target),
            project_name=project_name,
            result_dir=result_dir,
            export_dir=export_dir,
            tia_version=tia_version,
            plc_name=plc_name,
            publish_graph=publish_graph,
        )
    except FileNotFoundError as exc:
        return {"ok": False, "error": "not_found", "message": str(exc)}
    except (RuntimeError, ValueError) as exc:
        return {"ok": False, "error": "analyze_failed", "message": str(exc)}

    project = result["project"]
    return {
        "ok": True,
        "readonly": True,
        "project_name": project.name,
        "import": result.get("import"),
        "result_dir": result.get("result_dir") or "",
        "summary": project.summary(),
        "conversion_report": result.get("conversion_report"),
        "report": result["report"],
        "scl_sources": result["scl_sources"],
        "knowledge_graph": result["knowledge_graph"].to_json(),
        "graph_publish": result.get("graph_publish"),
        "extraction_notes": project.extraction_notes,
    }


@mcp.tool(name="plc.program.download")
def plc_program_download(**kwargs: Any) -> dict[str, Any]:
    """HIGH RISK — disabled by default and never auto-enabled."""
    if not _flag_enabled("RESEARCHOS_PLC_ALLOW_DOWNLOAD"):
        return {
            "ok": False,
            "error": "forbidden",
            "code": "PLC_DOWNLOAD_DISABLED",
            "message": (
                "Downloading programs to PLCs is disabled by default. "
                "ResearchOS output is advisory; apply changes via your "
                "change management process."
            ),
        }
    # Even with the flag, we intentionally do not implement device writes here.
    return {
        "ok": False,
        "error": "not_implemented",
        "code": "PLC_DOWNLOAD_NOT_IMPLEMENTED",
        "message": "Device write paths are intentionally absent from this stub.",
    }


@mcp.tool(name="plc.program.upload_suggest")
def plc_program_upload_suggest(**kwargs: Any) -> dict[str, Any]:
    """Generate a downloadable artifact for manual engineer import (flagged)."""
    if not _flag_enabled("RESEARCHOS_PLC_ALLOW_UPLOAD_SUGGEST"):
        return {
            "ok": False,
            "error": "forbidden",
            "code": "PLC_UPLOAD_SUGGEST_DISABLED",
            "message": "Disabled by default; enable explicitly and approve via HITL.",
        }
    return {
        "ok": False,
        "error": "not_implemented",
        "code": "PLC_UPLOAD_SUGGEST_NOT_IMPLEMENTED",
        "message": "Artifact generation is not implemented in this stub.",
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
