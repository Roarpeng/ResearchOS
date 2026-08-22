"""PLC project ingestion orchestration."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from gateway.app.config import get_settings

from gateway.app.services.plc.job_store import (
    _finish_progress,
    _append_progress,
    _now,
    _start_progress,
    get_job,
)
from gateway.app.services.plc.logic_graph import (
    _logic_graph_from_kg,
)

logger = logging.getLogger("researchos.gateway.plc")

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
                "is_safety": bool(getattr(block, "is_safety", False)),
            }
        )
    blocks.sort(key=lambda b: (b.get("type") or "", b.get("name") or ""))
    return blocks


def _annotate_block_nest_depth(job: dict[str, Any]) -> None:
    """Copy TYPED_AS nest_depth onto job.blocks for node cards / chat."""
    from agents.plc.tia.typed_as import nest_depth_of

    kg = job.get("knowledge_graph") or {}
    memo: dict[str, int] = {}
    for block in job.get("blocks") or []:
        name = str(block.get("name") or "")
        if not name:
            continue
        block["nest_depth"] = nest_depth_of(kg, name, _memo=memo)






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
                "timings": pipeline_timings,
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
        job["coverage"] = result.get("coverage") or {}
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
        _annotate_block_nest_depth(job)
        try:
            from agents.plc.tia.understanding import ensure_understanding

            ensure_understanding(job)
        except Exception as exc:  # noqa: BLE001
            logger.debug("engineer understanding seed skipped: %s", exc)
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
