"""PLC project importer — classify inputs and open .apxx via Openness.

Aligned with docs/agents/PLC Offline Analyzer Architecture.md:

- Level 1/2: already-exported SCL/XML folders (offline, no TIA needed)
- Level 3 (.apxx): not parsed as a binary DB; Openness exports SimaticML first

User-facing contract:

    .apxx  --(Openness)-->  SimaticML exports  --(offline)-->  PLC-IR -> SCL
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

APXX_SUFFIXES = {".ap17", ".ap18", ".ap19", ".ap20", ".apxx"}


@dataclass
class ImportResult:
    """Resolved path that `extract_project` can consume."""

    export_dir: Path
    source_kind: str  # "apxx" | "export_dir"
    project_path: Path | None = None
    tia_version: str = ""
    notes: list[str] | None = None

    def __post_init__(self) -> None:
        if self.notes is None:
            self.notes = []


def classify_input(path: str | Path) -> str:
    """Return 'apxx' | 'export_dir' | 'unknown' based on path shape."""
    p = Path(path).expanduser()
    if p.suffix.lower() in APXX_SUFFIXES:
        return "apxx"
    if p.is_dir():
        return "export_dir"
    return "unknown"


def _adapter_script() -> Path:
    root = Path(__file__).resolve().parents[3]
    return root / "industrial" / "tia_adapter" / "ExportProject.ps1"


def _infer_tia_version(project_path: Path, explicit: str = "") -> str:
    if explicit:
        return explicit
    env = os.getenv("RESEARCHOS_TIA_VERSION", "").strip()
    if env:
        return env
    m = re.search(r"\.ap(1[789]|20)$", project_path.suffix.lower())
    if m:
        return f"V{m.group(1)}"
    return "V17"


def export_apxx_via_openness(
    project_path: str | Path,
    *,
    export_dir: str | Path | None = None,
    tia_version: str = "",
    plc_name: str = "",
    timeout_s: int = 600,
) -> Path:
    """Run industrial/tia_adapter/ExportProject.ps1 against a .apxx file.

    Requires TIA Portal + Openness on this machine. Returns the export directory.
    """
    project = Path(project_path).expanduser().resolve()
    if not project.is_file():
        raise FileNotFoundError(f"TIA project not found: {project}")
    if project.suffix.lower() not in APXX_SUFFIXES:
        raise ValueError(f"Not a TIA project file (.ap17-.ap20): {project}")

    script = _adapter_script()
    if not script.is_file():
        raise FileNotFoundError(f"Openness adapter missing: {script}")

    out = Path(export_dir).expanduser() if export_dir else Path(
        tempfile.mkdtemp(prefix="researchos_tia_export_")
    )
    out.mkdir(parents=True, exist_ok=True)
    version = _infer_tia_version(project, tia_version)

    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "-ProjectPath",
        str(project),
        "-ExportDir",
        str(out),
        "-TiaVersion",
        version,
    ]
    if plc_name:
        cmd.extend(["-PlcName", plc_name])

    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(
            f"Openness export failed (exit {completed.returncode}). "
            f"Install TIA Portal Openness and join the Openness Windows group.\n{detail}"
        )
    return out


def resolve_project_input(
    path: str | Path,
    *,
    export_dir: str | Path | None = None,
    tia_version: str = "",
    plc_name: str = "",
    auto_export: bool = True,
) -> ImportResult:
    """Normalize user input to an Openness export directory.

    - Directory → use as export_dir (Level 1/2 offline)
    - .apxx → Openness export then return that folder (Level 3 via connector)
    """
    p = Path(path).expanduser().resolve()
    kind = classify_input(p)
    if kind == "export_dir":
        return ImportResult(export_dir=p, source_kind="export_dir", notes=[])
    if kind == "apxx":
        if not auto_export:
            raise ValueError(
                "Received .apxx but auto_export=False. Pass an Openness export "
                "directory, or enable auto_export to run ExportProject.ps1."
            )
        out = export_apxx_via_openness(
            p,
            export_dir=export_dir,
            tia_version=tia_version,
            plc_name=plc_name,
        )
        return ImportResult(
            export_dir=out,
            source_kind="apxx",
            project_path=p,
            tia_version=_infer_tia_version(p, tia_version),
            notes=[f"exported via Openness from {p}"],
        )
    raise FileNotFoundError(
        f"Unsupported PLC input: {p}. Provide a .ap17/.ap18/.ap19/.ap20 file "
        "or a SimaticML export directory."
    )
