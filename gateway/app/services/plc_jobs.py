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
            from agents.plc.tia.xml_understand import enrich_kg_calls_from_xml_files

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
        inouts: list[str] = []
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
            elif sec == "InOut":
                inouts.append(label)
            elif sec == "Static":
                statics.append(f"{label} : {dtype}" if dtype else label)
        attrs = getattr(block, "attributes", None) or {}
        instance_of = (
            str(attrs.get("InstanceOfName") or "").strip()
            or str(attrs.get("OfType") or "").strip()
            or str(attrs.get("OfBlock") or "").strip()
            or None
        )
        is_protected = bool(getattr(block, "is_protected", lambda: False)())
        is_iface_only = bool(getattr(block, "is_interface_only", lambda: False)())
        body_ok = bool(getattr(block, "has_program_body", lambda: True)())
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
                "inouts": inouts,
                "statics": statics,
                "members": members,
                "instance_of": instance_of,
                "protected": is_protected,
                "interface_only": is_iface_only,
                "body_available": body_ok,
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
        "optimize_plan": "",
        "source_xmls": [],
        "progress": [],
        "timings": {},
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
    duration_ms: int | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "step": step,
        "title": title,
        "detail": detail,
        "status": status,
        "at": _now().isoformat(),
    }
    if duration_ms is not None:
        entry["duration_ms"] = int(duration_ms)
    job.setdefault("progress", []).append(entry)
    job["updated_at"] = _now()
    return entry


def _start_progress(
    job: dict[str, Any],
    step: str,
    title: str,
    *,
    detail: str = "",
) -> dict[str, Any]:
    import time

    entry = _append_progress(job, step, title, detail=detail, status="running")
    entry["_t0"] = time.monotonic()
    return entry


def _finish_progress(
    job: dict[str, Any],
    *,
    detail: str | None = None,
    status: str = "done",
) -> int:
    import time

    progress = job.get("progress") or []
    if not progress:
        return 0
    entry = progress[-1]
    t0 = entry.pop("_t0", None)
    duration_ms = int((time.monotonic() - t0) * 1000) if isinstance(t0, (int, float)) else 0
    entry["duration_ms"] = duration_ms
    entry["status"] = status
    entry["at"] = _now().isoformat()
    if detail is not None:
        entry["detail"] = detail
    job["updated_at"] = _now()
    return duration_ms


def run_ingest_job(
    job_id: str,
    *,
    publish_graph: bool = True,
    plc_name: str = "",
    tia_version: str = "",
    result_root: str | None = None,
) -> dict[str, Any]:
    """Synchronously run plc.tia.ingest pipeline into the job record."""
    import time

    from agents.plc.tia.timings import timings_summary

    job = get_job(job_id)
    if job is None:
        raise KeyError(job_id)

    job["status"] = "running"
    job["progress"] = []
    job["timings"] = {}
    job["updated_at"] = _now()
    t_all = time.monotonic()
    _start_progress(
        job,
        "detect",
        "检测工程输入",
        detail=str(job.get("source_path") or ""),
    )

    settings = get_settings()
    work = Path(result_root or settings.plc_work_dir or tempfile.gettempdir()) / "researchos_plc_jobs" / job_id
    work.mkdir(parents=True, exist_ok=True)

    try:
        from agents.plc.tia.importer import resolve_project_input
        from agents.plc.tia.package import write_result_package
        from agents.plc.tia.pipeline import analyze_tia_exports, interpretation_report
        from agents.plc.tia.timings import merge_timings

        _finish_progress(job)
        _start_progress(
            job,
            "resolve",
            "解析输入（.zap / .apxx / XML）",
            detail="必要时调用 TIA Openness 导出 SimaticML",
        )
        t_resolve = time.monotonic()
        imported = resolve_project_input(
            job["source_path"],
            tia_version=tia_version,
            plc_name=plc_name,
            auto_export=True,
        )
        resolve_wall_ms = int((time.monotonic() - t_resolve) * 1000)
        pipeline_timings: dict[str, int] = merge_timings(
            {"resolve_wall_ms": resolve_wall_ms},
            imported.timings,
        )
        resolve_detail = (
            f"source_kind={imported.source_kind}; export_dir={imported.export_dir}"
        )[:240]
        fine = {
            k: pipeline_timings[k]
            for k in (
                "unzip_ms",
                "stage_copy_ms",
                "openness_cli_ms",
                "openness_open_ms",
                "openness_compile_ms",
                "openness_list_ms",
                "openness_blocks_export_ms",
                "openness_export_ms",
                "openness_skip_compile_ms",
                "openness_compile_retry_ms",
                "openness_cache_hit_ms",
                "openness_cache_hit",
                "resolve_wall_ms",
            )
            if k in pipeline_timings
        }
        if fine:
            resolve_detail = (resolve_detail + " | " + timings_summary(fine)).strip(" |")[:400]
        _finish_progress(job, detail=resolve_detail)

        if imported.project_path:
            job["project_path"] = str(imported.project_path)
        elif Path(str(job["source_path"])).suffix.lower() in {
            ".ap17", ".ap18", ".ap19", ".ap20", ".apxx",
        }:
            job["project_path"] = str(Path(str(job["source_path"])).resolve())
        job["openness_export_dir"] = str(imported.export_dir)

        name = job.get("project_name") or (
            imported.project_path.stem
            if imported.project_path
            else imported.export_dir.name
        )
        _start_progress(job, "ir", "构建 PLC-IR / 知识图谱 / SCL")
        result = analyze_tia_exports(
            str(imported.export_dir),
            project_name=name,
            publish_graph=publish_graph,
        )
        pipeline_timings = merge_timings(pipeline_timings, result.get("timings"))
        project = result["project"]
        for note in imported.notes or []:
            project.extraction_notes.append(note)
        if imported.tia_version:
            project.tia_version = imported.tia_version
        if imported.project_path:
            project.source_path = str(imported.project_path)

        t_pkg = time.monotonic()
        write_result_package(
            str(work / "package"),
            project=project,
            knowledge_graph=result["knowledge_graph"],
            scl_sources=result.get("scl_sources") or {},
            report_md=interpretation_report(project, result["knowledge_graph"]),
            extra_meta={
                "source_kind": imported.source_kind,
                "export_dir": str(imported.export_dir),
                "tia_version": imported.tia_version,
            },
        )
        pipeline_timings["package_ms"] = int((time.monotonic() - t_pkg) * 1000)

        kg = result["knowledge_graph"].to_json()
        job["project_name"] = project.name
        job["summary"] = project.summary()
        job["extraction_notes"] = list(project.extraction_notes or [])
        job["knowledge_graph"] = kg
        job["scl_sources"] = result.get("scl_sources") or {}
        job["folded_logic"] = result.get("folded_logic") or {}
        job["report"] = interpretation_report(project, result["knowledge_graph"])
        job["graph_publish"] = result.get("graph_publish")
        job["blocks"] = _block_list(project)
        job["export_dir"] = str(work / "package")
        job["export_ready"] = True
        ir_bits = {
            k: pipeline_timings[k]
            for k in (
                "extract_ms",
                "fold_attach_ms",
                "kg_ms",
                "scl_ms",
                "fold_serialize_ms",
                "package_ms",
                "neo4j_ms",
                "report_ms",
            )
            if k in pipeline_timings
        }
        _finish_progress(
            job,
            detail=(
                f"块数={len(job['blocks'])}"
                + (f" | {timings_summary(ir_bits)}" if ir_bits else "")
            )[:400],
        )

        # Prefer Openness export XMLs for write-back staging
        xml_root = job.get("openness_export_dir") or job["source_path"]
        job["source_xmls"] = _collect_source_xmls(str(xml_root))
        # XML CallInfo + optional LLM (evidence-gated) — never title/SCL heuristics
        import os

        from agents.plc.tia.xml_understand import enrich_kg_calls_from_xml_files

        _start_progress(
            job,
            "enrich",
            "XML CallInfo 补全 CALLS",
            detail=f"xmls={len(job['source_xmls'] or [])}",
        )
        t_enrich = time.monotonic()
        kg = enrich_kg_calls_from_xml_files(
            kg,
            xml_paths=job["source_xmls"] or [],
            known_blocks={str(b.get("name")) for b in job["blocks"] if b.get("name")},
            use_llm=bool(os.getenv("LITELLM_BASE_URL")),
        )
        enrich_ms = int((time.monotonic() - t_enrich) * 1000)
        pipeline_timings["enrich_ms"] = enrich_ms
        job["knowledge_graph"] = kg
        _finish_progress(job, detail=f"edges={len(kg.get('edges') or [])}; enrich_ms={enrich_ms}")

        _start_progress(job, "graph", "生成逻辑图")
        t_logic = time.monotonic()
        job["logic_graph"] = _logic_graph_from_kg(kg)
        logic_ms = int((time.monotonic() - t_logic) * 1000)
        pipeline_timings["logic_graph_ms"] = logic_ms
        _finish_progress(
            job,
            detail=(
                f"KG nodes={len(kg.get('nodes') or [])}, "
                f"edges={len(kg.get('edges') or [])}; "
                f"logic edges={len((job.get('logic_graph') or {}).get('edges') or [])}; "
                f"logic_graph_ms={logic_ms}"
            )[:400],
        )
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
        total_ms = int((time.monotonic() - t_all) * 1000)
        pipeline_timings["total_ms"] = total_ms
        job["timings"] = pipeline_timings
        _append_progress(
            job,
            "ready",
            "解析完成，可对话确认与写回",
            status="done",
            duration_ms=total_ms,
            detail=timings_summary(pipeline_timings)[:400],
        )
        logger.info(
            "PLC ingest timings job_id=%s %s",
            job_id,
            timings_summary(pipeline_timings),
        )
        job["status"] = "ready"
        job["error"] = None
    except Exception as exc:  # noqa: BLE001 — surface to API
        logger.exception("PLC ingest failed job_id=%s", job_id)
        job["status"] = "failed"
        job["error"] = str(exc)
        # Close any running progress step
        if (job.get("progress") or []) and job["progress"][-1].get("status") == "running":
            _finish_progress(job, detail=str(exc)[:240], status="failed")
        _append_progress(job, "failed", "解析失败", detail=str(exc)[:400], status="failed")
        job["timings"] = {
            **dict(job.get("timings") or {}),
            "total_ms": int((time.monotonic() - t_all) * 1000),
        }
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

    text = (message or "").strip()
    # Route optimization intents to evidence-gated optimizer (not bare「反写」alone)
    if any(k in text for k in ("优化", "optimize", "死块", "dead block")) or (
        ("反写" in text or "writeback" in text.lower())
        and any(k in text for k in ("优化", "逻辑", "工程", "项目"))
    ):
        return propose_job_optimize(job, block_name=block_name, message=text)

    cs = propose_changeset_from_message(
        message,
        block_name=block_name or "",
        job_context={"project_name": job.get("project_name"), "blocks": job.get("blocks")},
    )
    job["changeset"] = cs.to_dict()
    job["updated_at"] = _now()
    return job["changeset"]


def propose_job_optimize(
    job: dict[str, Any],
    *,
    block_name: str | None = None,
    message: str = "",
) -> dict[str, Any]:
    """Propose safe optimization changeset (analyst → annotate/comment/stage XML)."""
    from agents.plc.tia.optimize import propose_optimization_changeset

    _ = message
    cs = propose_optimization_changeset(job, focus_block=block_name or None)
    job["changeset"] = cs.to_dict()
    job["optimize_plan"] = next(
        (n[len("optimize_plan:") :] for n in cs.notes if str(n).startswith("optimize_plan:")),
        "",
    )
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
    target: Path | None = None
    if resolved_project:
        target = resolve_allowed_path(resolved_project, settings)
        if target.suffix.lower() not in {".ap17", ".ap18", ".ap19", ".ap20", ".apxx"}:
            raise ValueError(f"Write-back target must be a TIA .apxx project, got {target.suffix}")
    elif execute_openness_import:
        raise ValueError(
            "project_path required: pass in request or ingest from .zap/.apxx so job.project_path is set"
        )

    raw_cs = job.get("changeset")
    if not raw_cs:
        raise ValueError("No proposed changeset; call propose first")
    cs = PlcChangeSet.from_dict(raw_cs)

    result: dict[str, Any] = {
        "project_path": str(target) if target else None,
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
    staged_ops = [op for op in cs.ops if op.kind == "stage_xml_import"]
    comment_ops = [op for op in cs.ops if op.kind == "set_block_comment"]
    if xml_paths:
        sources = list(xml_paths)
    elif staged_ops or comment_ops:
        # Lookup pool for comment→XML resolve; bundle only stages matched files
        sources = list(job.get("source_xmls") or [])
        for op in staged_ops:
            if op.payload.get("xml_path"):
                sources.append(str(op.payload["xml_path"]))
    else:
        sources = list(job.get("source_xmls") or [])

    bundle = prepare_writeback(export_root, cs, sources)
    result["bundle_dir"] = str(bundle)

    if execute_openness_import:
        if target is None:
            raise ValueError("project_path required for Openness import")
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


def _strip_at_hint(message: str) -> str:
    """Extract `@…` mention body without trailing Chinese question phrases."""
    import re

    msg = message or ""
    at = re.search(r"@(.+)", msg)
    if not at:
        return ""
    remainder = at.group(1).strip()
    for sep in (
        " 这个",
        " 请描述",
        " 描述",
        " 有什么",
        " 做什么",
        " 作用",
        "？",
        "?",
        "\n",
        "。",
        "，",
    ):
        idx = remainder.find(sep)
        if idx > 0:
            remainder = remainder[:idx].strip()
            break
    return remainder.strip().strip("@").strip()


def _normalize_fb_type_name(raw: str) -> str:
    """Strip quotes from SimaticML data_type like `\"FB5009_AnalOut\"`."""
    s = (raw or "").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in {'"', "'"}:
        s = s[1:-1].strip()
    return s


def _lookup_instance_entity(job: dict[str, Any], query: str) -> dict[str, Any] | None:
    """Resolve multi-instance / external DB name from KG (not job.blocks).

    Returns evidence-only dict:
      name, parents, type_block, uses_callers, instance_of, variables, kg_block, evidence[]
    """
    q = (query or "").strip().strip("@").strip()
    if not q:
        return None
    kg = job.get("knowledge_graph") or {}
    nodes = list(kg.get("nodes") or [])
    edges = list(kg.get("edges") or [])
    ql = q.lower()

    variables: list[dict[str, Any]] = []
    for n in nodes:
        if n.get("type") != "Variable":
            continue
        props = n.get("props") if isinstance(n.get("props"), dict) else {}
        vname = str(props.get("name") or "")
        if vname.lower() != ql:
            continue
        # id: Variable::Parent::Name  or  Variable::Parent::Section::Name
        parts = str(n.get("id") or "").split("::")
        parent = parts[1] if len(parts) >= 3 else ""
        variables.append(
            {
                "id": n.get("id"),
                "name": vname,
                "parent": parent,
                "section": props.get("section"),
                "data_type": props.get("data_type"),
                "comment": props.get("comment") or "",
            }
        )

    kg_block = None
    for n in nodes:
        if n.get("type") != "Block":
            continue
        props = n.get("props") if isinstance(n.get("props"), dict) else {}
        bname = str(props.get("name") or str(n.get("id") or "").split("::")[-1])
        if bname.lower() != ql:
            continue
        kg_block = {"id": n.get("id"), "props": props}
        break

    if not variables and kg_block is None:
        return None

    bid = f"Block::{q}"
    # Prefer exact casing from KG
    if kg_block:
        q = str((kg_block.get("props") or {}).get("name") or q)
        bid = str(kg_block.get("id") or bid)
    elif variables:
        q = str(variables[0].get("name") or q)
        # keep query casing from variable name
        for v in variables:
            if str(v.get("name")):
                q = str(v["name"])
                break

    uses_callers: list[dict[str, Any]] = []
    instance_of: list[str] = []
    evidence: list[str] = []
    for e in edges:
        et = str(e.get("type") or "")
        src = str(e.get("source") or "")
        tgt = str(e.get("target") or "")
        props = e.get("props") if isinstance(e.get("props"), dict) else {}
        if et == "USES" and (tgt == bid or tgt.endswith(f"::{q}")):
            caller = src.split("::", 1)[-1] if "::" in src else src
            uses_callers.append(
                {
                    "caller": caller,
                    "evidence": props.get("evidence") or "",
                    "network": props.get("network") or "",
                }
            )
            ev = props.get("evidence") or "USES"
            net = props.get("network") or ""
            evidence.append(f"USES {caller}→{q}" + (f" ({ev})" if ev else "") + (f" @ {net}" if net else ""))
        if et == "INSTANCE_OF" and (src == bid or src.endswith(f"::{q}")):
            typ = tgt.split("::", 1)[-1] if "::" in tgt else tgt
            if typ and typ not in instance_of:
                instance_of.append(typ)
                evidence.append(f"INSTANCE_OF {q}→{typ}")

    type_block = instance_of[0] if instance_of else ""
    if not type_block:
        for v in variables:
            dt = _normalize_fb_type_name(str(v.get("data_type") or ""))
            if dt.upper().startswith("FB") or dt.upper().startswith("FC"):
                type_block = dt
                evidence.append(
                    f"Variable {v.get('parent')}::{q} data_type={v.get('data_type')}"
                )
                break

    parents = sorted({str(v.get("parent") or "") for v in variables if v.get("parent")})
    if not parents:
        parents = sorted({c["caller"] for c in uses_callers if c.get("caller")})

    # Only treat as instance if we have Variable and/or external/USES/INSTANCE_OF evidence
    props = (kg_block or {}).get("props") or {}
    is_external = bool(props.get("external"))
    if not variables and not uses_callers and not instance_of and not is_external:
        return None

    return {
        "kind": "instance",
        "name": q,
        "parents": parents,
        "type_block": type_block,
        "instance_of": instance_of,
        "uses_callers": uses_callers,
        "variables": variables,
        "kg_block": kg_block,
        "evidence": evidence,
    }


def _describe_instance_from_kg(job: dict[str, Any], entity: dict[str, Any]) -> str:
    """Evidence-gated description of a multi-instance / external instance node."""
    name = str(entity.get("name") or "")
    type_block = str(entity.get("type_block") or "")
    parents = list(entity.get("parents") or [])
    variables = list(entity.get("variables") or [])
    uses_callers = list(entity.get("uses_callers") or [])
    instance_of = list(entity.get("instance_of") or [])
    evidence = list(entity.get("evidence") or [])
    kg_block = entity.get("kg_block") if isinstance(entity.get("kg_block"), dict) else None
    blocks = {
        str(b["name"]): b
        for b in (job.get("blocks") or [])
        if isinstance(b, dict) and b.get("name")
    }

    lines: list[str] = [
        f"**`{name}`**（多实例成员 / 实例数据，非独立程序块）",
        "",
        "说明：该名称出现在知识图谱中，但**不在**工程 Blocks 导出列表中的独立 OB/FB/FC/DB。"
        "以下仅依据图谱边与接口节点，不推断未导出的内部逻辑。",
        "",
        "### 图谱定位",
    ]
    if kg_block:
        props = kg_block.get("props") or {}
        bits = [
            f"节点 `{kg_block.get('id')}`",
            f"标记 block_type=`{props.get('block_type')}`" if props.get("block_type") else "",
            "external=true" if props.get("external") else "",
        ]
        lines.append("- " + "；".join(b for b in bits if b))
    for v in variables[:6]:
        dt = v.get("data_type")
        sec = v.get("section")
        parent = v.get("parent")
        lines.append(
            f"- 接口变量 `{v.get('id') or f'Variable::{parent}::{name}'}`"
            + (f"：section=`{sec}`" if sec else "")
            + (f"，data_type=`{dt}`" if dt else "")
        )
    if parents:
        lines.append(f"- 所属父块：{', '.join(f'`{p}`' for p in parents)}")

    lines.append("")
    lines.append("### 类型与实例关系（边证据）")
    if instance_of:
        for t in instance_of:
            lines.append(f"- `INSTANCE_OF`：`{name}` → **`{t}`**")
    elif type_block:
        lines.append(f"- 类型（来自变量 data_type）：**`{type_block}`**")
    else:
        lines.append("- 图谱中**未找到** `INSTANCE_OF` 或可解析的 FB/FC data_type（无法断言类型块）。")

    if uses_callers:
        lines.append("- 调用/使用关系 `USES`：")
        for c in uses_callers[:8]:
            extra = []
            if c.get("evidence"):
                extra.append(str(c["evidence"]))
            if c.get("network"):
                extra.append(str(c["network"]))
            suffix = f"（{'；'.join(extra)}）" if extra else ""
            lines.append(f"  - `{c.get('caller')}` → `{name}`{suffix}")
    else:
        lines.append("- 未找到指向该实例的 `USES` 边。")

    # Type FB from IR — only facts from job.blocks / folded / IO
    type_name = type_block or (instance_of[0] if instance_of else "")
    if type_name and type_name in blocks:
        lines.append("")
        lines.append(f"### 类型块 `{type_name}`（PLC-IR 证据）")
        b = blocks[type_name]
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
        if meta:
            lines.append(f"- 元数据：{meta}")
        if b.get("comment"):
            lines.append(f"- 注释：{b.get('comment')}")
        lines.extend(_describe_block_function(job, type_name, b))
        lines.extend(_block_assoc_lines(job, type_name))
    elif type_name:
        lines.append("")
        lines.append(f"### 类型块 `{type_name}`")
        lines.append(
            f"- 图谱指向 `{type_name}`，但当前 job 的 Blocks/IR 中**没有**该块的接口与网络正文，"
            "故不描述其内部逻辑。"
        )

    if evidence:
        lines.append("")
        lines.append("### 依据摘要")
        for e in evidence[:12]:
            lines.append(f"- `{e}`")

    lines.append("")
    lines.append(
        "若需查看父块整体逻辑，请点击或 `@` "
        + (" / ".join(f"`{p}`" for p in parents[:3]) if parents else "父级 FB/DB")
        + "。"
    )
    return "\n".join(lines)


def _match_block_query(job: dict[str, Any], blocks: dict[str, Any], query: str) -> str:
    """Resolve a free-text query to a block name (exact / prefix / comment / network title)."""
    q = (query or "").strip().strip("@").strip()
    if not q or not blocks:
        return ""
    if q in blocks:
        return q
    ql = q.lower()
    for name in blocks:
        if name.lower() == ql:
            return name
    # Longest name contained in query, or query contained in name
    contained = [n for n in blocks if n.lower() in ql or ql in n.lower()]
    if len(contained) == 1:
        return contained[0]
    if contained:
        return max(contained, key=len)
    # Block comment / title
    for name, b in blocks.items():
        comment = str(b.get("comment") or "")
        if comment and (ql in comment.lower() or comment.lower() in ql):
            return name
    # SCL / folded network titles (often human-readable like "A Station CoolingFan")
    scl_sources = job.get("scl_sources") or {}
    for name, scl in scl_sources.items():
        if name not in blocks:
            continue
        for title in _network_titles_from_scl(str(scl or "")):
            tl = title.lower()
            if ql in tl or tl in ql:
                return name
    folded = job.get("folded_logic") or {}
    if isinstance(folded, dict):
        for name, nets in folded.items():
            if name not in blocks or not isinstance(nets, list):
                continue
            for net in nets:
                if not isinstance(net, dict):
                    continue
                title = str(net.get("title") or "").strip()
                if not title:
                    continue
                tl = title.lower()
                if ql in tl or tl in ql:
                    return name
    return ""


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

    if block_name:
        hit = _match_block_query(job, blocks, block_name)
        if hit:
            return hit

    msg = message or ""
    remainder = _strip_at_hint(msg)
    if remainder:
        # Prefer longest known block name as prefix of the mention
        for name in sorted(blocks.keys(), key=len, reverse=True):
            if remainder.lower().startswith(name.lower()):
                tail = remainder[len(name) :]
                if not tail or not tail[0].isalnum():
                    return name
        hit = _match_block_query(job, blocks, remainder)
        if hit:
            return hit

    # Bare name / comment / title inside the message (longer names first)
    for name in sorted(blocks.keys(), key=len, reverse=True):
        if len(name) <= 2:
            if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", msg, flags=re.IGNORECASE):
                return name
        elif name.lower() in msg.lower():
            return name

    # Last resort: match comment/title against whole message
    hit = _match_block_query(job, blocks, msg)
    if hit:
        return hit
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


def _block_network_titles(job: dict[str, Any], block_name: str) -> list[str]:
    """Human-readable network / step titles from folded_logic then SCL comments."""
    titles: list[str] = []
    seen: set[str] = set()
    folded = job.get("folded_logic") or {}
    nets = folded.get(block_name) if isinstance(folded, dict) else None
    if isinstance(nets, list):
        for net in nets:
            if not isinstance(net, dict):
                continue
            t = str(net.get("title") or "").strip().strip('"')
            if t and t not in seen:
                seen.add(t)
                titles.append(t)
    for t in _network_titles_from_scl(str((job.get("scl_sources") or {}).get(block_name) or "")):
        if t and t not in seen:
            seen.add(t)
            titles.append(t)
    return titles[:16]


def _call_relation_names(job: dict[str, Any], block_name: str) -> tuple[list[str], list[str]]:
    """Return (callers, callees) block names from KG CALLS edges."""
    callers: list[str] = []
    callees: list[str] = []
    bid = f"Block::{block_name}"
    for e in (job.get("knowledge_graph") or {}).get("edges") or []:
        if not isinstance(e, dict) or e.get("type") != "CALLS":
            continue
        src = str(e.get("source") or "")
        tgt = str(e.get("target") or "")
        if tgt == bid and src.startswith("Block::"):
            callers.append(src.split("::", 1)[-1])
        elif src == bid and tgt.startswith("Block::"):
            callees.append(tgt.split("::", 1)[-1])
    return sorted(set(callers)), sorted(set(callees))


def _explain_block_understanding(
    job: dict[str, Any],
    block_name: str,
    block: dict[str, Any],
    *,
    folded: list[str],
    reads: list[str],
    writes: list[str],
) -> str:
    """Narrative「理解」line — role in project, not a SCL dump."""
    comment = str(block.get("comment") or "").strip()
    titles = _block_network_titles(job, block_name)
    callers, callees = _call_relation_names(job, block_name)
    btype = str(block.get("type") or "块")
    bits: list[str] = [f"`{block_name}` 是工程中的 {btype}"]
    if comment:
        bits.append(f"注释为「{comment}」")
    if callers:
        bits.append("由 " + "、".join(f"`{c}`" for c in callers[:6]) + " 调用")
    if callees:
        bits.append("向下调用 " + "、".join(f"`{c}`" for c in callees[:8]))
    if titles:
        bits.append("主要网络/步序：" + " → ".join(titles[:10]))
    else:
        fold_purpose = _purpose_from_fold(folded, reads, writes)
        if fold_purpose and "无足够" not in fold_purpose:
            bits.append(fold_purpose.rstrip("。"))
    if reads or writes:
        io_bits = []
        if reads:
            io_bits.append("读 " + "、".join(reads[:6]))
        if writes:
            io_bits.append("写 " + "、".join(writes[:6]))
        bits.append("；".join(io_bits))
    return "；".join(bits) + "。"


def _format_scl_logic_block(statements: list[str]) -> list[str]:
    """Render folded statements as commented SCL fragment (fallback)."""
    if not statements:
        return []
    try:
        from agents.plc.tia.scl import explain_scl_statement
    except Exception:  # noqa: BLE001
        explain_scl_statement = lambda _s: ""  # type: ignore[misc, assignment]
    body: list[str] = []
    for raw in statements:
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
        if len(body) >= 24:
            break
    if not body:
        return []
    return ["主要逻辑（摘录，含中文说明）：", "```scl", *body, "```"]


def _format_block_scl_markdown(job: dict[str, Any], block_name: str) -> list[str]:
    """Full standard SCL unit (VAR_INPUT…END_VAR + commented body) — never truncate."""
    scl = str((job.get("scl_sources") or {}).get(block_name) or "").strip()
    if not scl:
        return []
    lines = scl.splitlines()
    return ["完整 SCL：", "```scl", *lines, "```"]


def _wants_full_scl(message: str) -> bool:
    msg = message or ""
    # Canvas deep-dive says「不要…完整 SCL」— that must NOT trigger a dump
    if re.search(r"不要.{0,16}(完整\s*SCL|粘贴|复述|只贴)", msg):
        return "展开 SCL" in msg or "贴出 SCL" in msg
    return any(
        k in msg
        for k in ("完整 SCL", "展开 SCL", "全部 SCL", "源码全文", "完整源码", "贴出 SCL", "全部代码")
    )


def _wants_block_explain(message: str) -> bool:
    msg = message or ""
    return any(
        k in msg
        for k in (
            "描述",
            "作用",
            "理解",
            "解释",
            "逻辑",
            "做什么",
            "干嘛",
            "功能",
            "深入",
            "分析",
        )
    )


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


def _block_io_lists(
    job: dict[str, Any], block_name: str, block: dict[str, Any]
) -> tuple[list[str], list[str], list[str]]:
    """Merge interface pins + Tag READS/WRITES (iface first)."""
    iface_in = [str(x) for x in (block.get("inputs") or []) if x]
    iface_out = [str(x) for x in (block.get("outputs") or []) if x]
    iface_inout = [str(x) for x in (block.get("inouts") or []) if x]
    reads, writes = _tag_io_for_block(job, block_name)
    if iface_in or iface_out or iface_inout:
        reads = (
            iface_in
            + iface_inout
            + [
                r
                for r in reads
                if r not in iface_in and r not in iface_inout and not r.startswith("#")
            ]
        )
        writes = (
            iface_out
            + iface_inout
            + [
                w
                for w in writes
                if w not in iface_out and w not in iface_inout and not w.startswith("#")
            ]
        )
    return reads, writes, iface_inout


def _join_capped(items: list[str], *, limit: int = 6) -> str:
    if not items:
        return "—"
    shown = items[:limit]
    more = f" 等{len(items)}个" if len(items) > limit else ""
    return ", ".join(shown) + more


def _wants_optimize_hints(message: str) -> bool:
    msg = message or ""
    return any(
        k in msg
        for k in ("优化", "改进", "风险", "死代码", "不可达", "建议改", "怎么改")
    )


def _wants_signal_trace(message: str) -> bool:
    msg = message or ""
    return any(
        k in msg
        for k in ("谁读写", "读写这些", "信号读写", "谁读", "谁写", "READS", "WRITES", "信号子图")
    )


def _format_signal_trace(job: dict[str, Any], block_name: str) -> list[str]:
    """Compact who-reads / who-writes for tags touched by this block."""
    reads, writes = _tag_io_for_block(job, block_name)
    tags = list(dict.fromkeys([*reads, *writes]))[:12]
    if not tags:
        return ["信号：该块暂无已验证 Tag READS/WRITES 边。"]
    lines = [f"**信号追踪（`{block_name}`）**"]
    kg = job.get("knowledge_graph") or {}
    for tag in tags:
        tid = f"Tag::{tag}"
        r_blocks: list[str] = []
        w_blocks: list[str] = []
        for e in kg.get("edges") or []:
            if str(e.get("target") or "") != tid:
                continue
            src = str(e.get("source") or "")
            if not src.startswith("Block::"):
                continue
            bname = src.split("::", 1)[-1]
            if e.get("type") == "READS":
                r_blocks.append(bname)
            elif e.get("type") == "WRITES":
                w_blocks.append(bname)
        lines.append(
            f"- `{tag}`：写={_join_capped(sorted(set(w_blocks)), limit=4)}；"
            f"读={_join_capped(sorted(set(r_blocks)), limit=4)}"
        )
    return lines


def _format_optimize_hints(job: dict[str, Any], block_name: str | None = None) -> list[str]:
    """Short actionable hints from evidence-gated analysis (no LLM dump)."""
    try:
        from agents.plc.tia.analyst import analyze_block, analyze_project

        result = analyze_block(job, block_name) if block_name else analyze_project(job)
    except Exception as exc:  # noqa: BLE001
        logger.warning("optimize hints skipped: %s", exc)
        return ["优化：分析暂不可用。"]
    findings = result.get("findings") or []
    lines = [f"**优化提示**" + (f"（`{block_name}`）" if block_name else "（工程）")]
    actionable = 0
    for f in findings:
        sev = str(f.get("severity") or "")
        if sev not in {"warn", "risk"}:
            continue
        msg = str(f.get("message") or "").strip()
        code = str(f.get("code") or "")
        if not msg:
            continue
        tip = {
            "DEAD_BLOCK": "核对是否仍需保留，或补上从 OB 的 CALLS。",
            "UNREACHABLE_FROM_OB": "检查调用链是否缺失 / 仅被注释掉。",
        }.get(code, "结合调用与 IO 再确认是否可简化。")
        lines.append(f"- [{sev}] {msg} → {tip}")
        actionable += 1
        if actionable >= 5:
            break
    if not actionable:
        lines.append("- 未发现 warn/risk 级发现；可点「优化提案」做逻辑级改写预览。")
    return lines


def _describe_block_function(
    job: dict[str, Any],
    block_name: str,
    block: dict[str, Any],
    *,
    include_full_scl: bool = False,
) -> list[str]:
    """Concise card: role / IO / calls / ≤5 steps. Full SCL only on demand.

    Target: ≤12 lines so canvas click answers stay scannable.
    """
    comment = str(block.get("comment") or "").strip()
    instance_of = str(block.get("instance_of") or "").strip()
    interface_only = bool(block.get("interface_only"))
    protected = bool(block.get("protected"))
    body_available = block.get("body_available")
    if body_available is None:
        body_available = not interface_only and not (
            protected and int(block.get("networks") or 0) == 0
        )
    reads, writes, iface_inout = _block_io_lists(job, block_name, block)
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
        ][:8]

    titles = _block_network_titles(job, block_name)
    callers, callees = _call_relation_names(job, block_name)
    lines: list[str] = []

    if interface_only or (protected and not body_available):
        lines.append("状态：接口开放 · 程序体不可用（不臆测内部逻辑）")
        purpose = comment or "封装功能块；结合接口与上下游调用理解角色。"
        lines.append(f"理解：{purpose}")
        lines.append(f"作用：{purpose}")
    else:
        understanding = _explain_block_understanding(
            job, block_name, block, folded=folded, reads=reads, writes=writes
        )
        # Keep「理解」to one short clause when possible
        if len(understanding) > 160:
            understanding = understanding[:157].rstrip("；。,，") + "…"
        lines.append(f"理解：{understanding}")
        lines.append(f"作用：{_purpose_from_fold(folded, reads, writes)}")

    lines.append(f"输入：{_join_capped(reads) if reads else '（无已验证读取）'}")
    lines.append(f"输出：{_join_capped(writes) if writes else '（无已验证写入）'}")
    if iface_inout and not (set(iface_inout) <= set(reads) & set(writes)):
        lines.append(f"InOut：{_join_capped(iface_inout, limit=4)}")

    call_bits: list[str] = []
    if callers:
        call_bits.append("被调用：" + _join_capped(callers, limit=4))
    if callees:
        call_bits.append("调用：" + _join_capped(callees, limit=4))
    if call_bits:
        lines.append("；".join(call_bits))
    elif instance_of:
        lines.append(f"实例类型：`{instance_of}`")

    step_titles = titles[:5]
    if step_titles:
        lines.append("逻辑：" + " → ".join(step_titles))
    elif folded:
        # One-line logic peek (no code fence)
        peek = folded[0]
        if len(peek) > 72:
            peek = peek[:69] + "…"
        lines.append(f"逻辑：`{peek}`" + (f" 等{len(folded)}条" if len(folded) > 1 else ""))

    for note in _block_risk_notes(job, block_name)[:1]:
        lines.append(f"注意：{note}")

    if interface_only or (protected and not body_available):
        lines.append("程序体：不可用（未解密 / 未导出）— 不做 SCL 展开")
    elif include_full_scl:
        lines.extend(_format_block_scl_markdown(job, block_name))
    elif (job.get("scl_sources") or {}).get(block_name):
        lines.append("_下一步：说「展开 SCL」看完整源码；或问「谁读写这些信号」/「优化建议」。_")
    else:
        lines.append("_下一步：可选中画布查看信号子图；或问「优化建议」。_")
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
    """Understand the user question, retrieve from KG, then answer (LLM if configured)."""
    import re

    blocks = {b["name"]: b for b in job.get("blocks") or [] if isinstance(b, dict) and b.get("name")}
    focus = _resolve_block_focus(job, message, block_name)
    msg = message or ""
    hint = (block_name or "").strip() or _strip_at_hint(msg)
    at = re.search(r"@(.+)", msg)

    # Explicit canvas/@ name that is NOT an IR block → multi-instance / external KG entity
    for candidate in (block_name, hint):
        cand = (candidate or "").strip()
        if not cand or cand in blocks:
            continue
        inst = _lookup_instance_entity(job, cand)
        if inst is not None:
            return _describe_instance_from_kg(job, inst)

    if (at or block_name) and not focus:
        show = (hint or block_name or "")[:80]
        lines = [
            f"未找到与 `@{show}` 匹配的**独立程序块**（Blocks 列表中的 OB/FB/FC/DB 名 / 注释 / 网络标题）。"
        ]
        near: list[str] = []
        ql = show.lower()
        for n in (job.get("knowledge_graph") or {}).get("nodes") or []:
            if n.get("type") not in {"Variable", "Block"}:
                continue
            props = n.get("props") if isinstance(n.get("props"), dict) else {}
            nm = str(props.get("name") or "")
            if nm and ql and (ql in nm.lower() or nm.lower() in ql) and nm not in near:
                near.append(nm)
            if len(near) >= 8:
                break
        if near:
            lines.append("图谱中有近似节点（可能是多实例成员）：" + ", ".join(f"`{n}`" for n in near))
        names = [b["name"] for b in (job.get("blocks") or [])[:12]]
        if names:
            lines.append(f"可试独立块：{', '.join(f'`{n}`' for n in names)}")
        lines.append("也可点击知识图谱节点；多实例成员会按图谱边（USES / INSTANCE_OF / 接口变量）作答。")
        return "\n".join(lines)

    # Single-block card for explicit @/canvas focus (not multi-topic questions)
    explicit_one = bool(block_name) or bool(at)
    multi_topic = any(
        k in msg for k in ("水平", "垂直", "向上", "向下", "整体", "架构", "比较", "作业", "哪些")
    )
    if focus and focus in blocks and explicit_one and not multi_topic:
        b = blocks[focus]
        include_scl = _wants_full_scl(msg)
        if _wants_signal_trace(msg) and not include_scl:
            return "\n".join(_format_signal_trace(job, focus))
        if _wants_optimize_hints(msg) and not include_scl:
            return "\n".join(_format_optimize_hints(job, focus))
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
        fact_lines = [f"**`{focus}`**（{meta}）" if meta else f"**`{focus}`**"]
        fact_lines.extend(
            _describe_block_function(job, focus, b, include_full_scl=include_scl)
        )
        # Concise by default: no LLM essay + evidence appendix on canvas click
        return "\n".join(fact_lines)

    # Project-level optimize without @block
    if _wants_optimize_hints(msg) and not at:
        return "\n".join(_format_optimize_hints(job, None))

    from agents.plc.tia.chat_retrieve import answer_query_with_kg

    history = []
    chat_turns = list(job.get("chat") or [])
    for turn in chat_turns[-8:]:
        if isinstance(turn, dict) and turn.get("content"):
            history.append(
                {"role": str(turn.get("role") or "user"), "content": str(turn.get("content"))}
            )
    return answer_query_with_kg(
        job,
        msg,
        focus_block=focus or None,
        chat_history=history,
    )


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
