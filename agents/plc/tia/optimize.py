"""Evidence-gated PLC optimization proposals → changeset (safe MVP).

Does **not** decrypt Know-how / invent LAD networks. Produces:
  - KG annotations + block comments for dead / risky blocks
  - staged XML with header-comment patches when source XML is available
  - optimize_plan.md narrative for HITL review before writeback→zap
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from agents.plc.tia.changeset import PlcChangeOp, PlcChangeSet


def _block_map(job: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(b["name"]): b
        for b in (job.get("blocks") or [])
        if isinstance(b, dict) and b.get("name")
    }


def _is_writable_body(block: dict[str, Any] | None) -> bool:
    if not block:
        return False
    if block.get("interface_only") or block.get("protected"):
        return False
    if block.get("body_available") is False:
        return False
    return True


def propose_optimization_changeset(
    job: dict[str, Any],
    *,
    focus_block: str | None = None,
    max_dead: int = 24,
) -> PlcChangeSet:
    """Build a proposed changeset from analyst findings + open-block metadata."""
    from agents.plc.tia.analyst import analyze_block, analyze_project
    from agents.plc.tia.xml_patch import match_xml_for_block

    blocks = _block_map(job)
    source_xmls = list(job.get("source_xmls") or [])
    ops: list[PlcChangeOp] = []
    notes: list[str] = []
    plan_lines: list[str] = [
        "# ResearchOS PLC 优化提案（HITL）",
        "",
        "范围：基于知识图谱证据的**安全优化**（注释/标注/可导入 XML 头注释）。",
        "不做：Know-how 解密、从零生成 LAD/FBD 网络、臆造 CALLS。",
        "",
    ]

    project = analyze_project(job)
    dead = list(project.get("dead_blocks") or [])[:max_dead]
    if dead:
        plan_lines.append("## 未从 OB 入口到达的块")
        for name in dead:
            b = blocks.get(name)
            btype = (b or {}).get("type") or "?"
            writable = _is_writable_body(b)
            msg = (
                f"[OPT] 未从 OB 入口到达（dead_block）。建议审查：删除/归档或补调用。"
                f" type={btype}"
            )
            ops.append(
                PlcChangeOp(
                    kind="annotate",
                    payload={"block_name": name, "text": msg},
                )
            )
            ops.append(
                PlcChangeOp(
                    kind="set_block_comment",
                    payload={"block_name": name, "comment": msg},
                )
            )
            xml = match_xml_for_block(name, source_xmls) if writable else None
            if xml is not None:
                ops.append(
                    PlcChangeOp(
                        kind="stage_xml_import",
                        payload={
                            "xml_path": str(xml),
                            "block_name": name,
                            "patch_comment": msg,
                        },
                    )
                )
                plan_lines.append(f"- `{name}`（{btype}）：标注 + 头注释写回 XML `{xml.name}`")
            elif not writable:
                plan_lines.append(
                    f"- `{name}`（{btype}）：仅图谱标注（interface_only/protected/无程序体，不改 XML）"
                )
            else:
                plan_lines.append(f"- `{name}`（{btype}）：图谱注释（未匹配到源 XML）")
            notes.append(f"optimize:dead_block:{name}")
        plan_lines.append("")

    focus = (focus_block or "").strip()
    if focus and focus in blocks:
        analysis = analyze_block(job, focus)
        plan_lines.append(f"## 焦点块 `{focus}`")
        b = blocks[focus]
        findings = analysis.get("findings") or []
        for f in findings:
            sev = f.get("severity") or "info"
            code = f.get("code") or ""
            message = str(f.get("message") or "").strip()
            if not message:
                continue
            plan_lines.append(f"- [{sev}] `{code}`：{message}")
            if sev in {"warn", "risk"}:
                text = f"[OPT:{code}] {message}"
                ops.append(
                    PlcChangeOp(
                        kind="annotate",
                        payload={"block_name": focus, "text": text},
                    )
                )
                notes.append(f"optimize:focus:{code}")
        if _is_writable_body(b) and any(
            (f.get("severity") in {"warn", "risk"}) for f in findings
        ):
            comment = (
                str(b.get("comment") or "").strip()
                or f"[OPT] 已审查焦点块 {focus}；详见图谱 annotations"
            )
            if not comment.startswith("[OPT"):
                comment = f"[OPT] {comment}"
            ops.append(
                PlcChangeOp(
                    kind="set_block_comment",
                    payload={"block_name": focus, "comment": comment},
                )
            )
            xml = match_xml_for_block(focus, source_xmls)
            if xml is not None:
                ops.append(
                    PlcChangeOp(
                        kind="stage_xml_import",
                        payload={
                            "xml_path": str(xml),
                            "block_name": focus,
                            "patch_comment": comment,
                        },
                    )
                )
        plan_lines.append("")

    # Document interface-only blocks as non-editable for writeback expectations
    iface_only = [
        n
        for n, b in blocks.items()
        if b.get("interface_only") or (b.get("protected") and not b.get("body_available"))
    ][:40]
    if iface_only:
        plan_lines.append("## 程序体不可写（跳过逻辑改写）")
        for name in iface_only:
            plan_lines.append(f"- `{name}`：接口开放 · 程序体不可用")
        plan_lines.append("")
        notes.append(f"optimize:interface_only_count:{len(iface_only)}")

    if not ops:
        notes.append("optimize:no_ops")
        plan_lines.append("_当前图谱未产生可自动落地的安全写回操作；可先手动改 XML 再「导入」。_")
    else:
        plan_lines.extend(
            [
                "## 下一步",
                "1. 人工审阅本提案与 changeset ops",
                "2. 确认 writeback（Openness Import + Save）",
                "3. Archive 下载新 `.zap`",
                "",
            ]
        )

    cs = PlcChangeSet(
        id=uuid.uuid4().hex[:12],
        ops=ops,
        status="proposed",
        notes=notes,
    )
    # Stash plan text on notes for API consumers (also written to bundle later)
    cs.notes.append("optimize_plan:" + "\n".join(plan_lines))
    return cs


def write_optimize_plan(bundle_dir: str | Path, changeset: PlcChangeSet) -> Path | None:
    """Extract optimize_plan from changeset notes into ``optimize_plan.md``."""
    plan = ""
    for n in changeset.notes:
        if isinstance(n, str) and n.startswith("optimize_plan:"):
            plan = n[len("optimize_plan:") :]
            break
    if not plan.strip():
        return None
    path = Path(bundle_dir) / "optimize_plan.md"
    path.write_text(plan, encoding="utf-8")
    return path
