"""Locate and invoke the TIA Openness MCP / CLI host (C# net481)."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def openness_server_project() -> Path:
    return (
        repo_root()
        / "tools"
        / "industrial-mcp"
        / "tia-openness"
        / "src"
        / "TiaOpenness.Server"
        / "TiaOpenness.Server.csproj"
    )


def find_openness_exe() -> Path | None:
    """Prefer an already-built Release/Debug exe; else None (caller may use `dotnet run`)."""
    override = os.getenv("RESEARCHOS_TIA_OPENNESS_EXE", "").strip()
    if override:
        p = Path(override).expanduser()
        return p if p.is_file() else None

    base = (
        repo_root()
        / "tools"
        / "industrial-mcp"
        / "tia-openness"
        / "src"
        / "TiaOpenness.Server"
        / "bin"
    )
    for cfg in ("Release", "Debug"):
        candidate = base / cfg / "net481" / "TiaOpenness.Server.exe"
        if candidate.is_file():
            return candidate
    return None


def _payload_text(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        parts: list[str] = []
        err = payload.get("error")
        if isinstance(err, dict) and err.get("message"):
            parts.append(str(err["message"]))
        elif err:
            parts.append(str(err))
        for key in ("message", "export", "import", "archive", "project"):
            val = payload.get(key)
            if isinstance(val, dict):
                nested = _payload_text(val)
                if nested:
                    parts.append(nested)
            elif isinstance(val, str) and val.strip():
                parts.append(val)
        return "\n".join(parts) if parts else json.dumps(payload, ensure_ascii=False)
    return str(payload)


def is_license_error(text: str) -> bool:
    t = (text or "").lower()
    return (
        "necessary license" in t
        or ("license" in t and ("missing" in t or "step 7" in t or "step7" in t))
        or "step 7 basic" in t
        or "step7 basic" in t
    )


def is_inconsistent_export_error(text: str) -> bool:
    """True when Openness refused export because blocks/UDTs are not compiled/consistent."""
    t = (text or "").lower()
    return (
        "inconsistent" in t
        or "isconsistent=false" in t.replace(" ", "")
        or "inconsistent_blocks" in t
    )


def format_openness_failure(
    payload_or_exc: Any,
    *,
    project_path: str | Path | None = None,
    action: str = "export",
) -> str:
    """Human-readable Openness failure; license errors are primary (not 'no XML')."""
    text = _payload_text(payload_or_exc)
    if isinstance(payload_or_exc, BaseException):
        text = str(payload_or_exc) or text
    proj = str(project_path) if project_path else ""
    if is_license_error(text):
        return (
            "TIA Openness 已打开工程，但操作失败：缺少必要许可证（如 STEP 7 Basic）。\n"
            "请在本机 Automation License Manager 安装/激活与 Portal 版本匹配的 "
            "STEP 7 / TIA 许可证后重试导出与写回。\n"
            + (f"工程: {proj}\n" if proj else "")
            + f"详情: {text}"
        )
    if action == "export" and is_inconsistent_export_error(text):
        return (
            "TIA Openness 已打开工程，但程序块/UDT 处于**不一致（Inconsistent）**状态，"
            "无法导出 SimaticML XML。\n"
            "Siemens Openness 只能导出已成功编译且 `IsConsistent=true` 的对象。\n\n"
            "请按下列步骤处理后重新上传：\n"
            "1) 用匹配版本的 TIA Portal 打开该工程（或 Project → Retrieve 打开 .zap）\n"
            "2) 右键 PLC → 编译 → 软件（仅）或全部，消除全部编译错误（含 UDT）\n"
            "3) 保存工程，再 Archive 为新的 `.zap`，或导出 Blocks XML\n"
            "4) 将新的 `.zap` / XML 上传到 ResearchOS\n\n"
            + (f"工程: {proj}\n" if proj else "")
            + f"详情: {text}"
        )
    action_cn = {
        "export": "导出 SimaticML XML",
        "import": "写回（Import）",
        "archive": "归档为 .zap",
    }.get(action, action)
    return (
        f"TIA Openness {action_cn}失败。\n"
        + (f"工程: {proj}\n" if proj else "")
        + f"详情: {text or payload_or_exc}"
    )


def openness_cli(
    *cli_args: str,
    timeout_s: int = 600,
) -> dict[str, Any]:
    """Run `TiaOpenness.Server --cli ...` and parse JSON stdout."""
    exe = find_openness_exe()
    csproj = openness_server_project()
    if exe is not None:
        cmd = [str(exe), "--cli", *cli_args]
        cwd = str(exe.parent)
    elif csproj.is_file():
        cmd = [
            "dotnet",
            "run",
            "--project",
            str(csproj),
            "-c",
            "Release",
            "--no-build",
            "--",
            "--cli",
            *cli_args,
        ]
        # If no-build fails, retry with build
        cwd = str(repo_root())
    else:
        raise FileNotFoundError(
            "TiaOpenness.Server not found. Build tools/industrial-mcp/tia-openness "
            "or set RESEARCHOS_TIA_OPENNESS_EXE."
        )

    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
        cwd=cwd,
    )
    if completed.returncode != 0 and exe is None and "--no-build" in cmd:
        cmd = [
            "dotnet",
            "run",
            "--project",
            str(csproj),
            "-c",
            "Release",
            "--",
            "--cli",
            *cli_args,
        ]
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
            cwd=cwd,
        )

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    payload: dict[str, Any]
    try:
        # CLI prints a single JSON object on stdout
        line = stdout.splitlines()[-1] if stdout else "{}"
        payload = json.loads(line)
    except json.JSONDecodeError:
        payload = {
            "ok": False,
            "error": {
                "code": "cli_parse_error",
                "message": stdout or stderr or "empty CLI output",
            },
        }

    if completed.returncode != 0 and payload.get("ok") is not False:
        payload.setdefault("ok", False)
        payload.setdefault(
            "error",
            {
                "code": "cli_exit",
                "message": stderr or f"exit {completed.returncode}",
            },
        )
    payload["_exit_code"] = completed.returncode
    if stderr:
        payload["_stderr"] = stderr[-2000:]
    return payload


def export_project_via_openness_cli(
    project_path: str | Path,
    *,
    export_dir: str | Path,
    tia_version: str = "",
    plc_name: str = "",
    timeout_s: int = 600,
) -> tuple[Path, list[str]]:
    """Export all blocks via C# Openness CLI; returns (export_dir, notes)."""
    project = Path(project_path).expanduser().resolve()
    out = Path(export_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    args = [
        "export-project",
        "--project",
        str(project),
        "--export-dir",
        str(out),
    ]
    if tia_version:
        args.extend(["--version", tia_version])
    if plc_name:
        args.extend(["--plc", plc_name])

    result = openness_cli(*args, timeout_s=timeout_s)
    notes: list[str] = []
    export = result.get("export") if isinstance(result.get("export"), dict) else {}
    msg = str((export or {}).get("message") or "").strip()
    if msg:
        notes.append(msg)
    # Prefer structured counts when present
    exported = (export or {}).get("exportedCount")
    failed = (export or {}).get("failedCount")
    if exported is not None or failed is not None:
        notes.append(
            f"Openness export counts: exported={exported or 0}, failed={failed or 0}"
        )
    if not result.get("ok"):
        raise RuntimeError(
            format_openness_failure(result, project_path=project, action="export")
        )
    return out, notes


def import_block_via_openness_cli(
    project_path: str | Path,
    xml_path: str | Path,
    *,
    plc_name: str = "",
    overwrite: bool = True,
    timeout_s: int = 600,
) -> dict[str, Any]:
    """Import one SimaticML block XML via ``--cli import-block`` (save inside CLI)."""
    project = Path(project_path).expanduser().resolve()
    xml = Path(xml_path).expanduser().resolve()
    if not xml.is_file():
        raise FileNotFoundError(f"Block XML not found: {xml}")

    args = [
        "import-block",
        "--project",
        str(project),
        "--xml",
        str(xml),
    ]
    if plc_name:
        args.extend(["--plc", plc_name])
    if not overwrite:
        args.append("--no-overwrite")

    result = openness_cli(*args, timeout_s=timeout_s)
    if not result.get("ok"):
        raise RuntimeError(
            format_openness_failure(result, project_path=project, action="import")
        )
    return result


def _zap_name_for_project(project: Path, explicit: str = "") -> str:
    if explicit:
        return Path(explicit).name
    m = re.search(r"\.ap(1[789]|20)$", project.suffix.lower())
    ver = m.group(1) if m else "19"
    return f"{project.stem}.zap{ver}"


def archive_project_via_openness_cli(
    project_path: str | Path,
    *,
    out: str | Path,
    tia_version: str = "",
    timeout_s: int = 600,
) -> Path:
    """Archive openable .apxx to a compressed .zap* via Openness CLI."""
    project = Path(project_path).expanduser().resolve()
    out_path = Path(out).expanduser().resolve()
    if out_path.suffix.lower().startswith(".zap") or out_path.suffix.lower() in {
        ".zap15",
        ".zap16",
        ".zap17",
        ".zap18",
        ".zap19",
        ".zap20",
    }:
        out_dir = out_path.parent
        name = out_path.name
    else:
        out_dir = out_path
        name = _zap_name_for_project(project)
    out_dir.mkdir(parents=True, exist_ok=True)

    args = [
        "archive-project",
        "--project",
        str(project),
        "--out-dir",
        str(out_dir),
        "--name",
        name,
    ]
    if tia_version:
        args.extend(["--version", tia_version])

    result = openness_cli(*args, timeout_s=timeout_s)
    if not result.get("ok"):
        raise RuntimeError(
            format_openness_failure(result, project_path=project, action="archive")
        )
    archive = result.get("archive") if isinstance(result.get("archive"), dict) else {}
    archived = Path(str((archive or {}).get("archivePath") or (out_dir / name)))
    if not archived.is_file():
        # Siemens may write without matching our exact name; pick newest zap in dir
        zaps = sorted(
            out_dir.glob("*.zap*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not zaps:
            raise RuntimeError(
                format_openness_failure(
                    {"message": f"Archive reported ok but no .zap found under {out_dir}"},
                    project_path=project,
                    action="archive",
                )
            )
        archived = zaps[0]
    return archived
