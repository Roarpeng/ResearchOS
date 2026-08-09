"""PLC Intelligence job service — feature module inside ResearchOS Gateway."""

from __future__ import annotations

import io
import json
import logging
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from gateway.app.config import Settings, get_settings
from gateway.app.services import store as mem
from agents.plc.tia.xml_understand import enrich_kg_calls_from_xml_files

logger = logging.getLogger("researchos.gateway.plc")

ALLOWED_UPLOAD_SUFFIXES = {
    ".xml",
    ".zip",
    ".zap",
    ".zap15",
    ".zap16",
    ".zap17",
    ".zap18",
    ".zap19",
    ".zap20",
    ".ap17",
    ".ap18",
    ".ap19",
    ".ap20",
    ".apxx",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _job_id() -> str:
    return f"plc_{uuid4().hex[:16]}"


def _allowlist_roots(settings: Settings) -> list[Path]:
    raw = (settings.plc_path_allowlist or "").strip()
    if not raw:
        # Dev default: temp + common project roots on the gateway host
        defaults = [
            Path(tempfile.gettempdir()),
            Path.cwd(),
            Path.home() / "Desktop" / "Project",
        ]
        return [p.resolve() for p in defaults if p.exists()]
    roots: list[Path] = []
    for part in raw.split(";"):
        part = part.strip()
        if not part:
            continue
        roots.append(Path(part).expanduser().resolve())
    return roots


def resolve_allowed_path(path: str, settings: Settings | None = None) -> Path:
    """Resolve path and enforce allowlist sandbox."""
    settings = settings or get_settings()
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(f"Path not found: {target}")
    roots = _allowlist_roots(settings)
    for root in roots:
        try:
            target.relative_to(root)
            return target
        except ValueError:
            continue
    raise PermissionError(
        f"Path not under PLC_PATH_ALLOWLIST. Allowed roots: {[str(r) for r in roots]}"
    )


def _is_ob_props(props: dict[str, Any], label: str = "") -> bool:
    bt = str(props.get("block_type") or props.get("type") or "").upper()
    name = label or str(props.get("name") or "")
    if bt == "OB":
        return True
    if re.match(r"^OB\d", name, re.I):
        return True
    if re.match(r"^(Startup|System|Pull|Rack|Main)\b", name, re.I):
        return True
    return False


def _logic_graph_from_kg(
    kg: dict[str, Any],
    *,
    max_dep_edges: int = 160,
) -> dict[str, Any]:
    """Build **逻辑图** (scan-cycle) from KG.

    Engineer view: which blocks Main/OB invokes each cycle — ordered CALLS + NEXT.
    Does **not** include internal implementation deps (nested CALLS, USES, INSTANCE_OF,
    DEPENDS_ON); those belong on the knowledge canvas via ``edges_from_plc_logic``.
    """
    del max_dep_edges  # kept for call-site compatibility; deps live on knowledge canvas
    blocks: list[dict[str, Any]] = []
    for n in kg.get("nodes") or []:
        if n.get("type") != "Block":
            continue
        props = n.get("props") or {}
        blocks.append(
            {
                "id": n["id"],
                "label": props.get("name") or n["id"].split("::")[-1],
                "type": "Block",
                "props": props,
            }
        )
    by_id = {b["id"]: b for b in blocks}
    ob_ids = {
        b["id"]
        for b in blocks
        if _is_ob_props(b.get("props") or {}, str(b.get("label") or ""))
    }

    # OB → callee CALLS only (top-level scan cycle)
    calls: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for e in kg.get("edges") or []:
        if str(e.get("type") or "") != "CALLS":
            continue
        src = str(e.get("source") or "")
        tgt = str(e.get("target") or "")
        if src not in ob_ids or tgt not in by_id or src == tgt:
            continue
        key = (src, tgt, "CALLS")
        if key in seen:
            continue
        seen.add(key)
        props = e.get("props") if isinstance(e.get("props"), dict) else {}
        item: dict[str, Any] = {"source": src, "target": tgt, "type": "CALLS", "weight": 1}
        if "seq" in props:
            item["seq"] = props["seq"]
        elif "seq" in e:
            item["seq"] = e["seq"]
        if props.get("evidence"):
            item["evidence"] = props["evidence"]
        calls.append(item)

    # NEXT between successive OB callees (prefer KG NEXT; else synthesize by seq)
    callee_seq: dict[str, list[tuple[int, str]]] = {oid: [] for oid in ob_ids}
    for c in calls:
        seq = int(c.get("seq") or 999)
        callee_seq.setdefault(c["source"], []).append((seq, c["target"]))
    for oid, lst in callee_seq.items():
        lst.sort(key=lambda x: (x[0], x[1]))

    next_edges: list[dict[str, Any]] = []
    kg_next = {
        (str(e.get("source")), str(e.get("target")))
        for e in (kg.get("edges") or [])
        if str(e.get("type") or "") == "NEXT"
    }
    for oid, lst in callee_seq.items():
        uniq: list[str] = []
        for _, tid in lst:
            if tid not in uniq:
                uniq.append(tid)
        for i in range(len(uniq) - 1):
            a, b = uniq[i], uniq[i + 1]
            key = (a, b, "NEXT")
            if key in seen:
                continue
            seen.add(key)
            next_edges.append(
                {
                    "source": a,
                    "target": b,
                    "type": "NEXT",
                    "weight": 1,
                    "seq": i + 1,
                    "evidence": "kg_next" if (a, b) in kg_next else "scan_cycle_order",
                }
            )

    keep_ids = set(ob_ids)
    for c in calls:
        keep_ids.add(c["source"])
        keep_ids.add(c["target"])
    # Always keep OBs even with no calls (show Main alone)
    nodes = [b for b in blocks if b["id"] in keep_ids]
    return {"nodes": nodes, "edges": calls + next_edges}


def refresh_logic_graph(job: dict[str, Any]) -> dict[str, Any]:
    """Recompute logic_graph from knowledge_graph (XML-derived edges only)."""
    kg = job.get("knowledge_graph")
    if isinstance(kg, dict) and (kg.get("nodes") or kg.get("edges")):
        # Optional: re-scan source XMLs + LLM validate CallInfo evidence
        xmls = []
        for p in job.get("source_xmls") or []:
            if isinstance(p, str):
                xmls.append(p)
        export_dir = job.get("openness_export_dir") or ""
        if export_dir:
            from pathlib import Path as _P

            root = _P(str(export_dir))
            if root.is_dir():
                xmls.extend(str(p) for p in root.rglob("*.xml"))
        if xmls:
            known = {
                str(b.get("name"))
                for b in (job.get("blocks") or [])
                if isinstance(b, dict) and b.get("name")
            }
            # Deterministic CallInfo always; LLM only if LiteLLM configured
            import os

            use_llm = bool(os.getenv("LITELLM_BASE_URL"))
            kg = enrich_kg_calls_from_xml_files(
                kg,
                xml_paths=xmls[:200],
                known_blocks=known,
                use_llm=use_llm,
            )
            job["knowledge_graph"] = kg
        job["logic_graph"] = _logic_graph_from_kg(kg)
    return job


def _block_list(project: Any) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for name, block in (getattr(project, "blocks", {}) or {}).items():
        interface = getattr(block, "interface", None) or []
        inputs: list[str] = []
        outputs: list[str] = []
        statics: list[str] = []
        members: list[str] = []
        for v in interface:
            section = getattr(v, "section", None)
            sec = getattr(section, "value", None) or str(section or "")
            var_name = getattr(v, "name", "") or ""
            dtype = getattr(v, "data_type", "") or ""
            if not var_name:
                continue
            label = f"#{var_name}"
            member = f"{var_name} : {dtype}" if dtype else var_name
            members.append(member)
            if sec == "Input":
                inputs.append(label)
            elif sec == "Output":
                outputs.append(label)
            elif sec == "Static":
                statics.append(f"{label} : {dtype}" if dtype else label)
        attrs = getattr(block, "attributes", None) or {}
        instance_of = (
            str(attrs.get("InstanceOfName") or "").strip()
            or str(attrs.get("OfType") or "").strip()
            or str(attrs.get("OfBlock") or "").strip()
            or None
        )
        blocks.append(
            {
                "name": name,
                "type": getattr(getattr(block, "block_type", None), "value", str(getattr(block, "block_type", ""))),
                "number": getattr(block, "number", None),
                "language": getattr(block, "programming_language", None),
                "networks": len(getattr(block, "networks", []) or []),
                "comment": (getattr(block, "header_comment", None) or "")[:240],
                "inputs": inputs,
                "outputs": outputs,
                "statics": statics,
                "members": members,
                "instance_of": instance_of,
            }
        )
    blocks.sort(key=lambda b: (b.get("type") or "", b.get("name") or ""))
    return blocks


def create_job_record(
    *,
    source_type: str,
    source_path: str,
    project_name: str,
    created_by: str,
    upload_filename: str | None = None,
) -> dict[str, Any]:
    now = _now()
    job = {
        "id": _job_id(),
        "status": "queued",
        "source_type": source_type,
        "source_path": source_path,
        "upload_filename": (upload_filename or "").strip() or None,
        "project_name": project_name,
        "created_by": created_by,
        "summary": {},
        "extraction_notes": [],
        "logic_graph": {"nodes": [], "edges": []},
        "knowledge_graph": {"nodes": [], "edges": []},
        "scl_sources": {},
        "folded_logic": {},
        "report": "",
        "graph_publish": None,
        "blocks": [],
        "chat": [],
        "export_dir": None,
        "export_ready": False,
        "project_path": None,
        "openness_export_dir": None,
        "changeset": None,
        "writeback": None,
        "source_xmls": [],
        "progress": [],
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
    with mem.store._lock:
        mem.store.plc_jobs[job["id"]] = job
    return job


def get_job(job_id: str) -> dict[str, Any] | None:
    return mem.store.plc_jobs.get(job_id)


def delete_job(job_id: str) -> bool:
    """Remove a PLC job from the in-memory store. Returns True if it existed."""
    with mem.store._lock:
        return mem.store.plc_jobs.pop(job_id, None) is not None


def query_job_graph(job: dict[str, Any], op: str, **params: Any) -> dict[str, Any]:
    """Run a deterministic query against a PLC job's knowledge graph."""
    from agents.plc.tia.graph_query import query

    return query(job.get("knowledge_graph") or {}, op, **params)


def list_jobs(limit: int = 20) -> list[dict[str, Any]]:
    jobs = list(mem.store.plc_jobs.values())
    jobs.sort(key=lambda j: j.get("created_at") or _now(), reverse=True)
    return jobs[: max(1, min(limit, 100))]


def _append_progress(
    job: dict[str, Any],
    step: str,
    title: str,
    *,
    detail: str = "",
    status: str = "done",
) -> None:
    job.setdefault("progress", []).append(
        {
            "step": step,
            "title": title,
            "detail": detail,
            "status": status,
            "at": _now().isoformat(),
        }
    )
    job["updated_at"] = _now()


def run_ingest_job(
    job_id: str,
    *,
    publish_graph: bool = True,
    plc_name: str = "",
    tia_version: str = "",
    result_root: str | None = None,
) -> dict[str, Any]:
    """Synchronously run plc.tia.ingest pipeline into the job record."""
    job = get_job(job_id)
    if job is None:
        raise KeyError(job_id)

    job["status"] = "running"
    job["progress"] = []
    job["updated_at"] = _now()
    _append_progress(
        job,
        "detect",
        "检测工程输入",
        detail=str(job.get("source_path") or ""),
        status="running",
    )

    settings = get_settings()
    work = Path(result_root or settings.plc_work_dir or tempfile.gettempdir()) / "researchos_plc_jobs" / job_id
    work.mkdir(parents=True, exist_ok=True)

    try:
        from agents.plc.tia import analyze_plc_project
        from agents.plc.tia.package import write_result_package

        job["progress"][-1]["status"] = "done"
        _append_progress(
            job,
            "resolve",
            "解析输入（.zap / .apxx / XML）",
            detail="必要时调用 TIA Openness 导出 SimaticML",
            status="running",
        )
        result = analyze_plc_project(
            job["source_path"],
            project_name=job.get("project_name") or "",
            result_dir=str(work / "package"),
            plc_name=plc_name,
            tia_version=tia_version,
            publish_graph=publish_graph,
        )
        project = result["project"]
        kg = result["knowledge_graph"].to_json()
        imp = result.get("import") or {}
        job["progress"][-1]["status"] = "done"
        job["progress"][-1]["detail"] = (
            f"source_kind={imp.get('source_kind') or 'export'}; "
            f"export_dir={imp.get('export_dir') or ''}"
        )[:240]
        if imp.get("project_path"):
            job["project_path"] = str(imp["project_path"])
        elif Path(str(job["source_path"])).suffix.lower() in {
            ".ap17", ".ap18", ".ap19", ".ap20", ".apxx",
        }:
            job["project_path"] = str(Path(str(job["source_path"])).resolve())
        if imp.get("export_dir"):
            job["openness_export_dir"] = str(imp["export_dir"])

        _append_progress(job, "ir", "构建 PLC-IR / 程序块", status="running")
        job["project_name"] = project.name
        job["summary"] = project.summary()
        job["extraction_notes"] = list(project.extraction_notes or [])
        job["knowledge_graph"] = kg
        job["scl_sources"] = result.get("scl_sources") or {}
        if result.get("folded_logic"):
            job["folded_logic"] = result["folded_logic"]
        job["report"] = result.get("report") or ""
        job["graph_publish"] = result.get("graph_publish")
        job["blocks"] = _block_list(project)
        job["export_dir"] = result.get("result_dir") or str(work / "package")
        job["export_ready"] = bool(job["export_dir"] and Path(job["export_dir"]).is_dir())
        # Prefer Openness export XMLs for write-back staging
        xml_root = job.get("openness_export_dir") or job["source_path"]
        job["source_xmls"] = _collect_source_xmls(str(xml_root))
        # XML CallInfo + optional LLM (evidence-gated) — never title/SCL heuristics
        import os

        kg = enrich_kg_calls_from_xml_files(
            kg,
            xml_paths=job["source_xmls"] or [],
            known_blocks={str(b.get("name")) for b in job["blocks"] if b.get("name")},
            use_llm=bool(os.getenv("LITELLM_BASE_URL")),
        )
        job["knowledge_graph"] = kg
        job["logic_graph"] = _logic_graph_from_kg(kg)
        job["progress"][-1]["status"] = "done"
        job["progress"][-1]["detail"] = f"块数={len(job['blocks'])}"

        _append_progress(
            job,
            "graph",
            "生成逻辑图与知识图谱",
            detail=(
                f"KG nodes={len(kg.get('nodes') or [])}, "
                f"edges={len(kg.get('edges') or [])}; "
                f"logic edges={len((job.get('logic_graph') or {}).get('edges') or [])}"
            ),
            status="done",
        )
        # Ensure package exists even if analyze skipped empty result_dir edge cases
        if not job["export_ready"]:
            write_result_package(
                str(work / "package"),
                project=project,
                knowledge_graph=result["knowledge_graph"],
                scl_sources=job["scl_sources"],
                report_md=job["report"],
            )
            job["export_dir"] = str(work / "package")
            job["export_ready"] = True
            if not job["source_xmls"]:
                job["source_xmls"] = _collect_source_xmls(str(xml_root))
        # Empty IR after ingesting a raw .zap/.apxx tree is a hard failure, not "ready".
        if not job["blocks"]:
            from agents.plc.tia.importer import (
                find_apxx_files,
                openness_unavailable_guidance,
            )
            from agents.plc.tia.openness_cli import format_openness_failure, is_license_error

            notes_blob = " ".join(job["extraction_notes"] or [])
            if is_license_error(notes_blob):
                raise RuntimeError(
                    format_openness_failure(
                        notes_blob,
                        project_path=job.get("project_path"),
                        action="export",
                    )
                )

            src = Path(str(job.get("project_path") or job["source_path"]))
            scan = src if src.is_dir() else src.parent
            apxx = find_apxx_files(scan) if scan.is_dir() else (
                [src] if src.suffix.lower() in {".ap17", ".ap18", ".ap19", ".ap20", ".apxx"} else []
            )
            if apxx:
                raise RuntimeError(openness_unavailable_guidance(apxx[0]))
            notes = "; ".join(job["extraction_notes"][:3]) if job["extraction_notes"] else ""
            raise RuntimeError(
                "未识别到任何 PLC 程序块或标签表，无法生成逻辑图/知识图谱。"
                + (f" 备注: {notes}" if notes else " 请上传 Openness 导出的 Blocks XML 或含 Blocks 的 ZIP。")
            )
        _append_progress(job, "ready", "解析完成，可对话确认与写回", status="done")
        job["status"] = "ready"
        job["error"] = None
    except Exception as exc:  # noqa: BLE001 — surface to API
        logger.exception("PLC ingest failed job_id=%s", job_id)
        job["status"] = "failed"
        job["error"] = str(exc)
        _append_progress(job, "failed", "解析失败", detail=str(exc)[:400], status="failed")
    job["updated_at"] = _now()
    return job


def _collect_source_xmls(source_path: str) -> list[str]:
    p = Path(source_path)
    if p.is_file() and p.suffix.lower() == ".xml":
        return [str(p.resolve())]
    if p.is_dir():
        return [str(x.resolve()) for x in sorted(p.rglob("*.xml"))][:200]
    return []


def propose_job_changeset(
    job: dict[str, Any],
    message: str,
    block_name: str | None = None,
) -> dict[str, Any]:
    from agents.plc.tia.changeset import propose_changeset_from_message

    cs = propose_changeset_from_message(
        message,
        block_name=block_name or "",
        job_context={"project_name": job.get("project_name"), "blocks": job.get("blocks")},
    )
    job["changeset"] = cs.to_dict()
    job["updated_at"] = _now()
    return job["changeset"]


def confirm_job_writeback(
    job: dict[str, Any],
    *,
    project_path: str | None = None,
    plc_name: str = "",
    accept_changeset: bool = True,
    execute_openness_import: bool = True,
    archive_zap: bool = True,
    xml_paths: list[str] | None = None,
) -> dict[str, Any]:
    """HITL: apply KG changeset, stage import bundle, optionally Openness import+save+archive."""
    from agents.plc.tia.changeset import PlcChangeSet, apply_changeset_to_kg
    from agents.plc.tia.openness_cli import archive_project_via_openness_cli
    from agents.plc.tia.writeback import execute_writeback, prepare_writeback

    settings = get_settings()
    resolved_project = (project_path or job.get("project_path") or "").strip()
    if not resolved_project:
        raise ValueError(
            "project_path required: pass in request or ingest from .zap/.apxx so job.project_path is set"
        )
    target = resolve_allowed_path(resolved_project, settings)
    if target.suffix.lower() not in {".ap17", ".ap18", ".ap19", ".ap20", ".apxx"}:
        raise ValueError(f"Write-back target must be a TIA .apxx project, got {target.suffix}")

    raw_cs = job.get("changeset")
    if not raw_cs:
        raise ValueError("No proposed changeset; call propose first")
    cs = PlcChangeSet.from_dict(raw_cs)

    result: dict[str, Any] = {
        "project_path": str(target),
        "changeset_id": cs.id,
        "kg_applied": False,
        "openness": None,
        "bundle_dir": None,
        "zap_path": None,
        "zap_archive": None,
    }

    if accept_changeset:
        cs.status = "accepted"
        kg = apply_changeset_to_kg(job.get("knowledge_graph") or {}, cs)
        job["knowledge_graph"] = kg
        job["logic_graph"] = _logic_graph_from_kg(kg)
        # Mirror comments onto block list
        for op in cs.ops:
            if op.kind == "set_block_comment":
                name = op.payload.get("block_name")
                for b in job.get("blocks") or []:
                    if b.get("name") == name:
                        b["comment"] = str(op.payload.get("comment") or "")[:240]
        result["kg_applied"] = True

    export_root = job.get("export_dir") or tempfile.mkdtemp(prefix="ros_plc_wb_")
    sources = list(xml_paths or []) or list(job.get("source_xmls") or [])
    # Also pick staged xml from changeset ops
    for op in cs.ops:
        if op.kind == "stage_xml_import" and op.payload.get("xml_path"):
            sources.append(str(op.payload["xml_path"]))

    bundle = prepare_writeback(export_root, cs, sources)
    result["bundle_dir"] = str(bundle)

    if execute_openness_import:
        if not list(bundle.glob("*.xml")):
            raise ValueError(
                "No XML staged for Openness import. Provide xml_paths or ingest from .xml first."
            )
        openness = execute_writeback(target, bundle, plc_name=plc_name)
        result["openness"] = openness
        if openness.get("ok"):
            cs.status = "applied"
        else:
            raise RuntimeError(f"Openness import failed: {openness}")

        if archive_zap and openness.get("ok"):
            out_dir = Path(export_root) / "archived"
            out_dir.mkdir(parents=True, exist_ok=True)
            try:
                zap_file = archive_project_via_openness_cli(target, out=out_dir)
                result["zap_path"] = str(zap_file)
                result["zap_archive"] = {"ok": True, "path": str(zap_file)}
            except Exception as exc:  # noqa: BLE001 — import succeeded; surface archive separately
                logger.exception("PLC zap archive failed job_id=%s", job.get("id"))
                result["zap_archive"] = {"ok": False, "error": str(exc)}
    else:
        cs.status = "accepted" if accept_changeset else cs.status
        result["openness"] = {
            "ok": True,
            "skipped": True,
            "note": "KG/bundle only; Openness import not requested",
        }

    job["changeset"] = cs.to_dict()
    job["writeback"] = result
    job["updated_at"] = _now()
    return result


def save_upload(filename: str | None, data: bytes, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    name = Path(filename or "upload.bin").name
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        raise ValueError(
            f"Unsupported upload type '{suffix}'. Allowed: {sorted(ALLOWED_UPLOAD_SUFFIXES)}"
        )
    if not data:
        raise ValueError("Uploaded file is empty")
    max_mb = int(settings.plc_upload_max_mb or 200)
    if len(data) > max_mb * 1024 * 1024:
        raise ValueError(f"Upload exceeds {max_mb} MB limit")

    # Lone .apxx cannot be Open()'d — require .zap or a zip of the full project tree.
    from agents.plc.tia.importer import APXX_SUFFIXES, incomplete_apxx_guidance

    if suffix in APXX_SUFFIXES:
        raise ValueError(incomplete_apxx_guidance(name))

    root = Path(settings.plc_work_dir or tempfile.gettempdir()) / "researchos_plc_uploads"
    root.mkdir(parents=True, exist_ok=True)
    dest = root / f"{uuid4().hex[:12]}_{name}"
    dest.write_bytes(data)

    if suffix == ".zip" or suffix == ".zap" or (
        suffix.startswith(".zap") and len(suffix) > 4 and suffix[4:].isdigit()
    ):
        from agents.plc.tia.importer import (
            extract_tia_archive,
            find_apxx_files,
            has_simaticml_exports,
            incomplete_apxx_guidance,
            is_complete_tia_project,
        )

        extract_dir = root / f"{dest.stem}_extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)
        extracted = extract_tia_archive(dest, dest=extract_dir)
        # After unpack: SimaticML XML is fine; bare incomplete .apxx is not.
        check_root = extracted if extracted.is_dir() else extracted.parent
        if not has_simaticml_exports(check_root):
            apxx = find_apxx_files(check_root)
            if apxx and not any(is_complete_tia_project(ap) for ap in apxx):
                raise ValueError(incomplete_apxx_guidance(apxx[0]))
        return extracted
    return dest


def _safe_extract_zip(zf: zipfile.ZipFile, dest: Path) -> None:
    """Extract zip members, rejecting path traversal (zip slip)."""
    dest_root = dest.resolve()
    for member in zf.infolist():
        target = (dest / member.filename).resolve()
        try:
            target.relative_to(dest_root)
        except ValueError as exc:
            raise ValueError(f"Zip slip rejected: {member.filename}") from exc
    zf.extractall(dest)


def _resolve_block_focus(
    job: dict[str, Any],
    message: str,
    block_name: str | None,
) -> str:
    """Resolve which PLC block the user is asking about."""
    import re

    blocks = {
        str(b["name"]): b
        for b in (job.get("blocks") or [])
        if isinstance(b, dict) and b.get("name")
    }
    if not blocks:
        return ""
    if block_name and block_name in blocks:
        return block_name
    # Exact match ignoring case
    if block_name:
        for name in blocks:
            if name.lower() == block_name.lower():
                return name
    msg = message or ""
    # @BlockName mention (from UI deep-dive)
    at = re.search(r"@([A-Za-z_][\w]*)", msg)
    if at:
        mentioned = at.group(1)
        if mentioned in blocks:
            return mentioned
        for name in blocks:
            if name.lower() == mentioned.lower():
                return name
    # Prefer longer names; short names (<=2) require word boundaries
    for name in sorted(blocks.keys(), key=len, reverse=True):
        if len(name) <= 2:
            if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", msg, flags=re.IGNORECASE):
                return name
        elif name.lower() in msg.lower():
            return name
    return ""


def _tag_io_for_block(job: dict[str, Any], block_name: str) -> tuple[list[str], list[str]]:
    reads: list[str] = []
    writes: list[str] = []
    bid = f"Block::{block_name}"
    for e in (job.get("knowledge_graph") or {}).get("edges") or []:
        if e.get("source") != bid:
            continue
        tag = str(e.get("target") or "")
        if not tag.startswith("Tag::"):
            continue
        name = tag.split("::", 1)[-1]
        if e.get("type") == "READS":
            reads.append(name)
        elif e.get("type") == "WRITES":
            writes.append(name)
    return sorted(set(reads)), sorted(set(writes))


def _network_titles_from_scl(scl: str) -> list[str]:
    titles: list[str] = []
    for line in (scl or "").splitlines():
        s = line.strip()
        if s.upper().startswith("// NETWORK"):
            # "// NETWORK 1: title"
            part = s.split(":", 1)
            title = part[1].strip() if len(part) > 1 else s
            if title:
                titles.append(title)
    return titles[:12]


def _expr_dict_to_scl(value: object) -> str:
    """Render folded_logic JSON expression trees back to SCL-like text."""
    if value is None:
        return "?"
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if not isinstance(value, dict):
        return str(value)
    kind = str(value.get("type") or value.get("kind") or "").lower()
    if kind in {"literal", "lit"}:
        lit = value.get("value")
        if lit is True:
            return "TRUE"
        if lit is False:
            return "FALSE"
        return str(lit)
    if kind == "ref":
        acc = value.get("access")
        if isinstance(acc, str):
            return acc
        if isinstance(acc, dict):
            return str(acc.get("scl") or acc.get("name") or "?")
        return str(value.get("scl") or "?")
    if kind == "not":
        return f"NOT ({_expr_dict_to_scl(value.get('operand'))})"
    if kind == "and":
        ops = value.get("operands") or []
        if not ops:
            return "?"
        if len(ops) == 1:
            return _expr_dict_to_scl(ops[0])
        return " AND ".join(f"({_expr_dict_to_scl(o)})" for o in ops)
    if kind == "or":
        ops = value.get("operands") or []
        if not ops:
            return "?"
        if len(ops) == 1:
            return _expr_dict_to_scl(ops[0])
        return " OR ".join(f"({_expr_dict_to_scl(o)})" for o in ops)
    if kind == "compare":
        return f"({_expr_dict_to_scl(value.get('lhs'))} {value.get('op')} {_expr_dict_to_scl(value.get('rhs'))})"
    if value.get("scl"):
        return str(value["scl"])
    return str(value)


def _folded_logic_lines(job: dict[str, Any], block_name: str) -> list[str]:
    folded = job.get("folded_logic") or {}
    networks = folded.get(block_name) if isinstance(folded, dict) else None
    if not isinstance(networks, list):
        return []
    out: list[str] = []
    for net in networks[:8]:
        if not isinstance(net, dict):
            continue
        title = str(net.get("title") or net.get("network_id") or "")
        for stmt in (net.get("statements") or [])[:12]:
            if not isinstance(stmt, dict):
                continue
            target = str(stmt.get("target") or stmt.get("target_scl") or "?")
            expr = _expr_dict_to_scl(stmt.get("value"))
            kind = str(stmt.get("kind") or "coil")
            if kind == "call":
                line = target.rstrip(";")
            elif kind == "move":
                en = stmt.get("enable")
                if en:
                    line = f"IF {_expr_dict_to_scl(en)} THEN {target} := {expr}; END_IF"
                else:
                    line = f"{target} := {expr}"
            elif kind == "neg_coil":
                line = f"{target} := NOT ({expr})"
            elif kind == "set":
                line = f"IF {expr} THEN {target} := TRUE; END_IF"
            elif kind == "reset":
                line = f"IF {expr} THEN {target} := FALSE; END_IF"
            elif kind == "coil" and " AND " not in expr and " OR " not in expr and expr not in {
                "TRUE",
                "FALSE",
                "?",
            }:
                line = f"IF {expr} THEN {target} := TRUE; ELSE {target} := FALSE; END_IF"
            else:
                line = f"{target} := {expr}"
            out.append(f"[{title}] {line}" if title else line)
            if len(out) >= 16:
                return out
    return out


def _purpose_from_fold(folded: list[str], reads: list[str], writes: list[str]) -> str:
    """One-line purpose guess from folded assignments / IO (evidence only)."""
    if len(folded) == 1 and ":=" in folded[0]:
        return f"将 `{folded[0].split(':=', 1)[0].strip()}` 赋值为 `{folded[0].split(':=', 1)[1].strip()}`。"
    if len(folded) > 1:
        return f"含 {len(folded)} 条已折叠赋值/布尔表达式。"
    if writes and reads:
        return f"读取 {', '.join(reads[:8])}，写入 {', '.join(writes[:8])}。"
    if writes:
        return f"写入 {', '.join(writes[:8])}。"
    if reads:
        return f"读取 {', '.join(reads[:8])}。"
    return "当前无足够 READS/WRITES 或折叠逻辑可归纳作用。"


def _format_scl_logic_block(statements: list[str]) -> list[str]:
    """Render folded statements as commented SCL fragment (fallback)."""
    if not statements:
        return []
    try:
        from agents.plc.tia.scl import explain_scl_statement
    except Exception:  # noqa: BLE001
        explain_scl_statement = lambda _s: ""  # type: ignore[misc, assignment]
    body: list[str] = []
    for raw in statements[:16]:
        line = str(raw).strip()
        if line.startswith("[") and "]" in line:
            line = line.split("]", 1)[1].strip()
        if not line:
            continue
        if not line.endswith(";"):
            line = f"{line};"
        meaning = explain_scl_statement(line)
        if meaning:
            body.append(f"// {meaning}")
        body.append(line)
    if not body:
        return []
    return ["逻辑：", "```scl", *body, "```"]


def _format_block_scl_markdown(job: dict[str, Any], block_name: str) -> list[str]:
    """Prefer full standard SCL unit (VAR_INPUT…END_VAR + commented body)."""
    scl = str((job.get("scl_sources") or {}).get(block_name) or "").strip()
    if not scl:
        return []
    # Keep chat readable; still show complete unit for typical FC/FB sizes
    lines = scl.splitlines()
    if len(lines) > 120:
        lines = lines[:120] + ["// …（已截断，完整 SCL 见导出包）"]
    return ["SCL：", "```scl", *lines, "```"]


def _block_assoc_lines(job: dict[str, Any], block_name: str) -> list[str]:
    """CALLS / USES associations for engineer-facing graph summary."""
    kg = job.get("knowledge_graph") or {}
    blocks = {
        b["name"]: b
        for b in (job.get("blocks") or [])
        if isinstance(b, dict) and b.get("name")
    }
    node_type = {
        (n.get("props") or {}).get("name") or n["id"].split("::")[-1]: (n.get("props") or {}).get(
            "block_type"
        )
        for n in (kg.get("nodes") or [])
        if n.get("type") == "Block" and isinstance(n, dict) and n.get("id")
    }

    def _label(name: str) -> str:
        bt = node_type.get(name) or (blocks.get(name) or {}).get("type") or ""
        return f"{name}（{bt}）" if bt else name

    callers: list[str] = []
    callees: list[str] = []
    uses: list[str] = []
    used_by: list[str] = []
    bid = f"Block::{block_name}"
    for e in kg.get("edges") or []:
        et = e.get("type")
        src = str(e.get("source") or "")
        tgt = str(e.get("target") or "")
        if et == "CALLS" and tgt == bid and src.startswith("Block::"):
            callers.append(_label(src.split("::", 1)[-1]))
        elif et == "CALLS" and src == bid and tgt.startswith("Block::"):
            callees.append(_label(tgt.split("::", 1)[-1]))
        elif et == "USES" and src == bid and tgt.startswith("Block::"):
            uses.append(_label(tgt.split("::", 1)[-1]))
        elif et == "USES" and tgt == bid and src.startswith("Block::"):
            used_by.append(_label(src.split("::", 1)[-1]))

    lines: list[str] = []
    if callers:
        lines.append(f"被调用：{', '.join(sorted(set(callers)))}")
    if callees:
        lines.append(f"调用：{', '.join(sorted(set(callees)))}")
    if uses:
        lines.append(f"使用：{', '.join(sorted(set(uses)))}")
    if used_by:
        lines.append(f"被使用：{', '.join(sorted(set(used_by)))}")
    return lines


def _describe_block_function(job: dict[str, Any], block_name: str, block: dict[str, Any]) -> list[str]:
    """Concise Chinese description: purpose / IO / logic (Markdown SCL)."""
    comment = str(block.get("comment") or "").strip()
    iface_in = [str(x) for x in (block.get("inputs") or []) if x]
    iface_out = [str(x) for x in (block.get("outputs") or []) if x]
    statics = [str(x) for x in (block.get("statics") or []) if x]
    instance_of = str(block.get("instance_of") or "").strip()
    reads, writes = _tag_io_for_block(job, block_name)
    if iface_in or iface_out:
        reads = iface_in + [r for r in reads if r not in iface_in and not r.startswith("#")]
        writes = iface_out + [w for w in writes if w not in iface_out and not w.startswith("#")]
    folded = _folded_logic_lines(job, block_name)
    if not folded:
        scl = (job.get("scl_sources") or {}).get(block_name) or ""
        folded = [
            ln.strip().rstrip(";")
            for ln in scl.splitlines()
            if (":=" in ln or "=>" in ln or "(" in ln)
            and not ln.strip().startswith("//")
            and not ln.strip().startswith("(*")
            and not ln.strip().upper().startswith("NETWORK")
            and "VAR" not in ln.upper().split()[:1]
        ][:12]

    lines: list[str] = []
    if comment:
        lines.append(f"注释：{comment}")
    if instance_of:
        lines.append(f'实例类型：FB `{instance_of}`')
    lines.append(f"作用：{_purpose_from_fold(folded, reads, writes)}")
    lines.append(f"输入：{', '.join(reads) if reads else '（无已验证读取标签）'}")
    lines.append(f"输出：{', '.join(writes) if writes else '（无已验证写入标签）'}")
    if statics:
        lines.append(f"静态/多实例：{', '.join(statics)}")
    scl_md = _format_block_scl_markdown(job, block_name)
    if scl_md:
        lines.extend(scl_md)
    else:
        lines.extend(_format_scl_logic_block(folded))
    # Instance DB has no networks — surface typed FB logic for engineers
    if instance_of and instance_of != block_name:
        fb_scl = _format_block_scl_markdown(job, instance_of)
        if fb_scl:
            lines.append(f"类型 FB `{instance_of}` 逻辑：")
            # drop the leading "SCL：" label from helper
            if fb_scl and fb_scl[0] == "SCL：":
                lines.extend(fb_scl[1:])
            else:
                lines.extend(fb_scl)
    return lines


def _block_risk_notes(job: dict[str, Any], block_name: str) -> list[str]:
    """Compact risk/warn lines for chat (no full evidence appendix)."""
    try:
        from agents.plc.tia.analyst import analyze_block

        findings = analyze_block(job, block_name).get("findings") or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("PLC risk notes skipped: %s", exc)
        return []
    notes: list[str] = []
    for f in findings:
        sev = str(f.get("severity") or "")
        if sev not in {"warn", "risk"}:
            continue
        msg = str(f.get("message") or "").strip()
        if msg:
            notes.append(msg)
    return notes[:4]


def answer_block_chat(job: dict[str, Any], message: str, block_name: str | None) -> str:
    """Deterministic PLC Q&A from IR/KG — concise content only."""
    blocks = {b["name"]: b for b in job.get("blocks") or [] if isinstance(b, dict) and b.get("name")}
    focus = _resolve_block_focus(job, message, block_name)

    lines: list[str] = []
    if focus and focus in blocks:
        b = blocks[focus]
        meta = " · ".join(
            p
            for p in [
                str(b.get("type") or ""),
                f"编号 {b.get('number')}" if b.get("number") is not None else "",
                str(b.get("language") or ""),
                f"{b.get('networks')} 网络" if b.get("networks") is not None else "",
            ]
            if p
        )
        lines.append(f"**`{focus}`**（{meta}）" if meta else f"**`{focus}`**")
        lines.extend(_describe_block_function(job, focus, b))
        lines.extend(_block_assoc_lines(job, focus))
        for note in _block_risk_notes(job, focus):
            lines.append(f"注意：{note}")
    else:
        names = [b["name"] for b in (job.get("blocks") or [])[:20]]
        lines.append(f"**{job.get('project_name') or '工程'}** · {job.get('summary')}")
        if names:
            lines.append(f"块：{', '.join(names)}")
        lines.append("点击节点或发送 `@块名 描述功能` 可深入单块。")
    return "\n".join(lines)


def analyze_job(job: dict[str, Any], *, block_name: str | None = None) -> dict[str, Any]:
    """Run deterministic, evidence-gated PLC analysis without any LLM call."""
    from agents.plc.tia.analyst import analyze_block, analyze_project

    return analyze_block(job, block_name) if block_name else analyze_project(job)


def build_export_zip(job: dict[str, Any]) -> bytes:
    export_dir = job.get("export_dir")
    if not export_dir or not Path(export_dir).is_dir():
        raise FileNotFoundError("Export package not ready")
    buf = io.BytesIO()
    root = Path(export_dir)
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in root.rglob("*"):
            if path.is_file():
                zf.write(path, arcname=str(path.relative_to(root)))
        # Also include logic graph snapshot
        zf.writestr(
            "ui_snapshots/logic_graph.json",
            json.dumps(job.get("logic_graph") or {}, ensure_ascii=False, indent=2),
        )
    return buf.getvalue()


def append_chat_turn(
    job: dict[str, Any],
    *,
    role: str,
    content: str,
    block_name: str | None = None,
) -> None:
    job.setdefault("chat", []).append(
        {
            "role": role,
            "content": content,
            "block_name": block_name,
            "created_at": _now(),
        }
    )
    job["updated_at"] = _now()
