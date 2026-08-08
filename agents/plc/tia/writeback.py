"""PLC write-back orchestration — import bundle → Openness CLI import."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.plc.tia.changeset import PlcChangeSet, write_import_bundle
from agents.plc.tia.openness_cli import import_block_via_openness_cli


def prepare_writeback(
    job_export_dir: str | Path,
    changeset: PlcChangeSet,
    source_xmls: list[str | Path] | None = None,
) -> Path:
    """Build ``{job_export_dir}/import_bundle`` and return that directory."""
    bundle = Path(job_export_dir).expanduser().resolve() / "import_bundle"
    write_import_bundle(bundle, changeset, source_xmls)
    return bundle


def _staged_xmls(bundle_dir: Path) -> list[Path]:
    manifest = bundle_dir / "staged_xmls.json"
    if manifest.is_file():
        raw = json.loads(manifest.read_text(encoding="utf-8"))
        return [Path(p) for p in raw if Path(p).is_file()]
    return sorted(bundle_dir.glob("*.xml"))


def execute_writeback(
    project_path: str | Path,
    bundle_dir: str | Path,
    plc_name: str = "",
) -> dict[str, Any]:
    """Import each staged XML via Openness CLI (project save is inside CLI)."""
    bundle = Path(bundle_dir).expanduser().resolve()
    xmls = _staged_xmls(bundle)
    results: list[dict[str, Any]] = []
    ok = True
    for xml in xmls:
        try:
            payload = import_block_via_openness_cli(
                project_path,
                xml,
                plc_name=plc_name,
                overwrite=True,
            )
            results.append({"xml": str(xml), "result": payload})
        except Exception as exc:  # noqa: BLE001
            results.append({"xml": str(xml), "result": {"ok": False, "error": str(exc)}})
            ok = False
            continue
        if not payload.get("ok"):
            ok = False

    return {
        "ok": ok,
        "project_path": str(Path(project_path).expanduser().resolve()),
        "bundle_dir": str(bundle),
        "imported": len(results),
        "results": results,
        "note": "project save is performed inside the Openness CLI import-block command",
    }
