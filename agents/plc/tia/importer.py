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
import zipfile
from dataclasses import dataclass
from pathlib import Path

APXX_SUFFIXES = {".ap17", ".ap18", ".ap19", ".ap20", ".apxx"}

# Siemens keeps project data beside the .apxx — a lone uploaded file cannot be Open()'d.
_TIA_SIDECAR_DIRS = ("System", "IM", "AdditionalFiles", "UserFiles", "TMP")


def is_tia_archive_suffix(suffix: str) -> bool:
    """True for .zip and Siemens project archives (.zap / .zap16 / .zap19 / …)."""
    s = (suffix or "").lower()
    if s in {".zip", ".zap"}:
        return True
    return bool(s.startswith(".zap") and len(s) > 4 and s[4:].isdigit())


def is_complete_tia_project(project_file: str | Path) -> bool:
    """True when ``.apxx`` sits in a full TIA project tree (not a lone file).

    TIA Openness ``Projects.Open`` requires the project file **and** its sibling
    project data (same-stem folder and/or System/IM/…). Uploading only
    ``test1.ap19`` into a temp folder always fails with「指定的路径无效」.
    """
    p = Path(project_file).expanduser().resolve()
    if not p.is_file() or p.suffix.lower() not in APXX_SUFFIXES:
        return False
    parent = p.parent
    if (parent / p.stem).is_dir():
        return True
    for name in _TIA_SIDECAR_DIRS:
        if (parent / name).is_dir():
            return True
    siblings = [
        item
        for item in parent.iterdir()
        if item.name != p.name
        and not item.name.startswith("_researchos")
        and not item.name.endswith("_extracted")
    ]
    return len(siblings) >= 1


def incomplete_apxx_guidance(project_file: str | Path | None = None) -> str:
    """Actionable Chinese guidance when a bare ``.apxx`` cannot be opened."""
    name = Path(project_file).name if project_file else ".ap19/.apxx"
    return (
        f"无法打开孤立的 TIA 工程文件 `{name}`。\n"
        "`.ap19/.apxx` 不是自包含文件：必须与同目录下的工程数据"
        "（同名文件夹、`System`/`IM` 等）一起交给 Openness。\n\n"
        "正确做法（按推荐顺序）：\n"
        "1) 【推荐】上传 TIA 归档 `.zap` / `.zap19`（已压缩完整工程，可直接解析）。\n"
        "2) 将**整个工程目录**打成 `.zip`（包含 `.ap19` 及旁边所有文件/文件夹）再上传。\n"
        "3) 本机路径解析：在允许目录下传入完整工程文件夹或其中的 `.ap19`（旁路文件须仍在）。\n"
        "4) 或导出 SimaticML XML / 含 `Blocks/*.xml` 的导出目录后上传（无需 Openness）。\n\n"
        "不要只上传单个 `.ap19` 文件。"
    )


def stage_tia_project_tree(
    project_file: str | Path,
    *,
    dest: str | Path | None = None,
) -> Path:
    """Copy the full project tree next to ``.apxx`` into a staging folder.

    Returns the staged ``.apxx`` path Openness should open. Raises if the
    source tree is incomplete.
    """
    import shutil

    src = Path(project_file).expanduser().resolve()
    if not is_complete_tia_project(src):
        raise ValueError(incomplete_apxx_guidance(src))

    parent = src.parent
    out_root = Path(dest).expanduser().resolve() if dest else Path(
        tempfile.mkdtemp(prefix="researchos_tia_project_")
    )
    out_root.mkdir(parents=True, exist_ok=True)
    staged_apxx = out_root / src.name

    # Copy entire parent contents so System / same-stem folder stay together.
    for item in parent.iterdir():
        if item.name.startswith("_researchos"):
            continue
        target = out_root / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)

    if not staged_apxx.is_file():
        raise FileNotFoundError(f"Staged project missing {src.name} under {out_root}")
    return staged_apxx


@dataclass
class ImportResult:
    """Resolved path that `extract_project` can consume."""

    export_dir: Path
    source_kind: str  # "apxx" | "export_dir" | "export_xml" | "archive"
    project_path: Path | None = None
    tia_version: str = ""
    notes: list[str] | None = None

    def __post_init__(self) -> None:
        if self.notes is None:
            self.notes = []


def classify_input(path: str | Path) -> str:
    """Return 'apxx' | 'archive' | 'export_dir' | 'export_xml' | 'unknown'."""
    p = Path(path).expanduser()
    if is_tia_archive_suffix(p.suffix):
        return "archive"
    if p.suffix.lower() in APXX_SUFFIXES:
        return "apxx"
    if p.is_file() and p.suffix.lower() == ".xml":
        return "export_xml"
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
) -> tuple[Path, list[str]]:
    """Export a .apxx via Openness.

    Preference order:
    1. C# TiaOpenness.Server CLI (`RESEARCHOS_TIA_OPENNESS=cli|auto`, default auto)
    2. PowerShell industrial/tia_adapter/ExportProject.ps1

    Requires TIA Portal + Openness on this machine. Returns (export_dir, notes).
    """
    project = Path(project_path).expanduser().resolve()
    if not project.is_file():
        raise FileNotFoundError(f"TIA project not found: {project}")
    if project.suffix.lower() not in APXX_SUFFIXES:
        raise ValueError(f"Not a TIA project file (.ap17-.ap20): {project}")
    if not is_complete_tia_project(project):
        raise ValueError(incomplete_apxx_guidance(project))

    # Stage a full tree copy so Openness never sees a lone .apxx in upload temp.
    try:
        project = stage_tia_project_tree(project)
        notes_stage = [f"staged complete TIA project tree for Openness: {project.parent}"]
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 — fall back to in-place open if copy fails
        notes_stage = [f"project staging skipped ({exc}); opening in place: {project}"]

    out = Path(export_dir).expanduser() if export_dir else Path(
        tempfile.mkdtemp(prefix="researchos_tia_export_")
    )
    out.mkdir(parents=True, exist_ok=True)
    version = _infer_tia_version(project, tia_version)

    mode = os.getenv("RESEARCHOS_TIA_OPENNESS", "auto").strip().lower() or "auto"
    notes: list[str] = list(notes_stage)
    if mode in {"cli", "mcp", "csharp", "auto"}:
        try:
            from agents.plc.tia.openness_cli import export_project_via_openness_cli

            path, cli_notes = export_project_via_openness_cli(
                project,
                export_dir=out,
                tia_version=version,
                plc_name=plc_name,
                timeout_s=timeout_s,
            )
            return path, [*notes, *cli_notes]
        except Exception:
            if mode != "auto":
                raise
            # fall through to PowerShell

    script = _adapter_script()
    if not script.is_file():
        raise FileNotFoundError(f"Openness adapter missing: {script}")

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
        from agents.plc.tia.openness_cli import format_openness_failure

        raise RuntimeError(
            format_openness_failure(
                detail or f"Openness PS1 export exit {completed.returncode}",
                project_path=project,
                action="export",
            )
        )
    notes.append(f"exported via Openness PowerShell from {project}")
    return out, notes


def _safe_extract_zip(archive: Path, dest: Path) -> None:
    dest_root = dest.resolve()
    with zipfile.ZipFile(archive, "r") as zf:
        for member in zf.infolist():
            target = (dest / member.filename).resolve()
            try:
                target.relative_to(dest_root)
            except ValueError as exc:
                raise ValueError(f"Zip slip rejected: {member.filename}") from exc
        zf.extractall(dest)


def find_apxx_files(root: Path) -> list[Path]:
    root = root.resolve()
    found = [
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in APXX_SUFFIXES
    ]
    found.sort(key=lambda p: (len(p.parts), str(p)))
    return found


def _looks_like_simaticml_xml(path: Path) -> bool:
    """True for Openness block/tag/UDT XML — not ConversionLog / GSDML junk."""
    name_u = path.name.upper()
    if name_u.startswith("GSDML") or "CONVERSIONLOG" in name_u:
        return False
    parts_l = {p.lower() for p in path.parts}
    if "gsd" in parts_l:
        return False
    try:
        head = path.read_bytes()[:8192].decode("utf-8", errors="ignore")
    except OSError:
        return False
    markers = (
        "SW.Blocks.",
        "SW.Tags.",
        "SW.DataTypes.",
        "DocumentType",
        "PlcStruct",
        "TagTable",
    )
    return any(m in head for m in markers)


def has_simaticml_exports(root: Path) -> bool:
    """Whether a tree contains real SimaticML program/tag exports."""
    root = root.resolve()
    for blocks in root.rglob("Blocks"):
        if blocks.is_dir() and any(blocks.glob("*.xml")):
            return True
    for xml in root.rglob("*.xml"):
        if _looks_like_simaticml_xml(xml):
            return True
    return False


def diagnose_extracted_tree(root: Path) -> dict[str, object]:
    """Summarize what a unpacked .zap/.zip contains — drives user guidance."""
    root = root.resolve()
    xmls = sorted(root.rglob("*.xml"))
    apxx = find_apxx_files(root)
    has_blocks = any(
        b.is_dir() and any(b.glob("*.xml")) for b in root.rglob("Blocks")
    )
    has_simatic = has_simaticml_exports(root)
    if has_simatic:
        mode = "simaticml"
    elif apxx:
        mode = "apxx_needs_openness"
    else:
        mode = "empty_or_unknown"
    return {
        "root": str(root),
        "xml_count": len(xmls),
        "apxx_files": [str(p) for p in apxx[:20]],
        "has_blocks_xml": has_blocks,
        "has_simaticml": has_simatic,
        "mode": mode,
    }


def openness_unavailable_guidance(apxx: Path | None = None) -> str:
    name = apxx.name if apxx else ".apxx"
    return (
        f".zap 已解压，但得到的是二进制工程 {name}，没有 SimaticML XML。\n"
        "ResearchOS 离线解析只读 Openness/人工导出的 XML，不能直接读 .apxx 数据库。\n\n"
        "可选方案（按推荐顺序）：\n"
        "1) 【推荐·无 Openness】在 TIA Portal：Project → Retrieve 打开 .zap → "
        "导出程序块为 XML（或整站 Export），再把 XML/含 Blocks 的 ZIP 上传到 ResearchOS。\n"
        "2) 【本机有 TIA】安装 Openness，用 Windows 宿主 Gateway（非 Linux 容器）解析，"
        "管线会自动 .zap→.apxx→Openness→XML。\n"
        "3) 【仅交换工程】请同事直接提供 Openness 导出目录或 SimaticML XML，而不是只给 .zap。\n"
        "说明：工程包内的 ConversionLog / GSDML 等 XML 不是程序逻辑；"
        "把 .zap 改名为 .zip 只能解压出 .apxx，仍然不能离线读逻辑。"
    )


def pick_project_root_from_extracted(root: Path) -> Path:
    """After unpacking .zip/.zap*, choose the best path for resolve_project_input.

    Preference:
    1. Directory that looks like a SimaticML export (Blocks/*.xml or SW.Blocks XML)
    2. A .apxx project file (needs Openness) — do NOT treat ConversionLog/GSD as export
    3. The extraction root itself
    """
    root = root.resolve()
    for blocks in root.rglob("Blocks"):
        if blocks.is_dir() and any(blocks.glob("*.xml")):
            return blocks.parent
    if has_simaticml_exports(root):
        return root
    apxx_files = find_apxx_files(root)
    if apxx_files:
        return apxx_files[0]
    return root


def extract_tia_archive(archive: str | Path, *, dest: str | Path | None = None) -> Path:
    """Extract Siemens .zap* / .zip project archive; return resolved project root."""
    archive_path = Path(archive).expanduser().resolve()
    if not archive_path.is_file():
        raise FileNotFoundError(f"Archive not found: {archive_path}")
    if not is_tia_archive_suffix(archive_path.suffix):
        raise ValueError(f"Not a TIA/ZIP archive: {archive_path}")

    out = Path(dest).expanduser() if dest else Path(
        tempfile.mkdtemp(prefix="researchos_tia_zap_")
    )
    out.mkdir(parents=True, exist_ok=True)
    try:
        _safe_extract_zip(archive_path, out)
    except zipfile.BadZipFile as exc:
        raise ValueError(
            f"无法把 {archive_path.name} 当 ZIP 解压（.zap 通常是 ZIP，但文件可能损坏、"
            f"加密或非标准封装）。请用 7-Zip 试解压；若失败请在 TIA 中 Project→Retrieve。"
            f" 底层错误: {exc}"
        ) from exc
    picked = pick_project_root_from_extracted(out)
    diag = diagnose_extracted_tree(out if picked.is_file() else picked)
    # Attach diagnosis via a sidecar note file for operators
    (out / "_researchos_zap_diag.json").write_text(
        __import__("json").dumps(diag, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return picked


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
    - Single .xml → wrap as a one-file export folder
    - .zap / .zip → extract (ZIP-based Siemens archive), then recurse
    - .apxx → Openness export then return that folder
    """
    p = Path(path).expanduser().resolve()
    kind = classify_input(p)
    if kind == "archive":
        extracted = extract_tia_archive(p)
        try:
            nested = resolve_project_input(
                extracted,
                export_dir=export_dir,
                tia_version=tia_version,
                plc_name=plc_name,
                auto_export=auto_export,
            )
        except Exception as exc:
            from agents.plc.tia.openness_cli import format_openness_failure, is_license_error

            msg = str(exc)
            # Bare / incomplete .apxx tree — surface packaging guidance first.
            if "孤立的 TIA 工程" in msg:
                raise
            # Openness already ran (license / export failure): surface that, don't wrap as "no XML".
            if is_license_error(msg) or "TIA Openness" in msg or "Openness" in msg:
                ap = extracted if extracted.is_file() else None
                if ap is None:
                    aps = find_apxx_files(extracted if extracted.is_dir() else extracted.parent)
                    ap = aps[0] if aps else None
                raise RuntimeError(
                    format_openness_failure(exc, project_path=ap, action="export")
                ) from exc
            diag_root = extracted if extracted.is_dir() else extracted.parent
            diag = diagnose_extracted_tree(diag_root)
            if diag.get("mode") == "apxx_needs_openness":
                ap_list = diag.get("apxx_files") or []
                ap = Path(str(ap_list[0])) if ap_list else None
                if ap is not None and not is_complete_tia_project(ap):
                    raise ValueError(incomplete_apxx_guidance(ap)) from exc
                raise RuntimeError(openness_unavailable_guidance(ap)) from exc
            raise
        nested.notes = list(nested.notes or [])
        nested.notes.insert(0, f"extracted Siemens archive {p.name} → {extracted}")
        return nested
    if kind == "export_dir":
        # Raw TIA project folders (from .zap) often contain ConversionLog/GSD XML + .apxx.
        # Do not treat those junk XMLs as SimaticML exports.
        if not has_simaticml_exports(p):
            apxx_files = find_apxx_files(p)
            if apxx_files:
                # Prefer a complete project file inside the folder (full tree).
                complete = next((ap for ap in apxx_files if is_complete_tia_project(ap)), None)
                if complete is None:
                    raise ValueError(incomplete_apxx_guidance(apxx_files[0]))
                return resolve_project_input(
                    complete,
                    export_dir=export_dir,
                    tia_version=tia_version,
                    plc_name=plc_name,
                    auto_export=auto_export,
                )
        return ImportResult(export_dir=p, source_kind="export_dir", notes=[])
    if kind == "export_xml":
        staging = Path(tempfile.mkdtemp(prefix="researchos_tia_xml_"))
        target = staging / p.name
        target.write_bytes(p.read_bytes())
        return ImportResult(
            export_dir=staging,
            source_kind="export_xml",
            project_path=p,
            notes=[f"single SimaticML XML staged from {p}"],
        )
    if kind == "apxx":
        if not auto_export:
            raise ValueError(
                "Received .apxx but auto_export=False. Pass an Openness export "
                "directory, or enable auto_export to run TIA Openness export."
            )
        if not is_complete_tia_project(p):
            raise ValueError(incomplete_apxx_guidance(p))
        try:
            out, export_notes = export_apxx_via_openness(
                p,
                export_dir=export_dir,
                tia_version=tia_version,
                plc_name=plc_name,
            )
        except Exception as exc:
            from agents.plc.tia.openness_cli import format_openness_failure, is_license_error

            msg = str(exc)
            if "孤立的 TIA 工程" in msg or "incomplete" in msg.lower():
                raise
            if is_license_error(msg) or "TIA Openness" in msg or "Openness" in msg:
                wrapped = format_openness_failure(exc, project_path=p, action="export")
                if any(
                    token in msg
                    for token in ("指定的路径", "Unable to open the project", "路径无效")
                ):
                    wrapped = incomplete_apxx_guidance(p) + "\n\n---\nOpenness 原始错误：\n" + wrapped
                raise RuntimeError(wrapped) from exc
            raise RuntimeError(
                openness_unavailable_guidance(p) + f"\n\nOpenness 错误: {exc}"
            ) from exc
        notes = [f"exported via Openness from {p}", *export_notes]
        return ImportResult(
            export_dir=out,
            source_kind="apxx",
            project_path=p,
            tia_version=_infer_tia_version(p, tia_version),
            notes=notes,
        )
    raise FileNotFoundError(
        f"Unsupported PLC input: {p}. Provide a .zap/.zap19 archive, "
        ".ap17/.ap18/.ap19/.ap20 file, a SimaticML .xml export, or an export directory."
    )
