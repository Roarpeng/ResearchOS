"""Evidence-gated block cards, SCL retrieval, and signal traces for chat."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from gateway.app.services.plc.chat_intents import (
    _normalize_fb_type_name,
    _strip_at_hint,
)

logger = logging.getLogger("researchos.gateway.plc")


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
    last_title = ""
    for raw in statements:
        line = str(raw).strip()
        title = ""
        if line.startswith("[") and "]" in line:
            title, line = line[1:].split("]", 1)
            title = title.strip()
            line = line.strip()
        if not line:
            continue
        if title and title != last_title:
            body.append(f"// 网络：{title}")
            last_title = title
        if not line.endswith(";"):
            line = f"{line};"
        meaning = explain_scl_statement(line)
        if meaning:
            body.append(f"// {meaning}")
        body.append(line)
        if len(body) >= 28:
            break
    if not body:
        return []
    return ["主要逻辑（摘录，含中文说明）：", "```scl", *body, "```"]


def _block_meta(job: dict[str, Any], block_name: str) -> dict[str, Any]:
    for b in job.get("blocks") or []:
        if isinstance(b, dict) and str(b.get("name") or "") == block_name:
            return b
    return {}


def _program_body_unavailable_reason(block: dict[str, Any] | None) -> str:
    b = block or {}
    if b.get("interface_only"):
        return "程序体不可用（接口开放 / interface_only）"
    if b.get("protected"):
        return "程序体不可用（Know-how / 保护）"
    if b.get("body_available") is False:
        return "程序体不可用（未导出）"
    if b.get("is_safety"):
        return "程序体不可用（Safety / F 块不展开）"
    return "程序体不可用（无已导出 SCL / 无折叠语句）"


def _folded_scl_dump(job: dict[str, Any], block_name: str) -> str:
    """Whatever folded / TODO SCL we already have — not new Siemens semantics."""
    lines: list[str] = []
    folded = job.get("folded_logic") or {}
    nets = folded.get(block_name) if isinstance(folded, dict) else None
    if isinstance(nets, list):
        for net in nets:
            if not isinstance(net, dict):
                continue
            title = str(net.get("title") or net.get("network_id") or "").strip()
            if title:
                lines.append(f"// NETWORK: {title}")
            for stmt in net.get("statements") or []:
                if isinstance(stmt, dict):
                    target = str(stmt.get("target") or stmt.get("target_scl") or "").strip()
                    kind = str(stmt.get("kind") or "coil")
                    expr = _expr_dict_to_scl(stmt.get("value"))
                    if kind == "call":
                        piece = target.rstrip(";")
                    elif kind == "move":
                        en = stmt.get("enable")
                        if en:
                            piece = f"IF {_expr_dict_to_scl(en)} THEN {target} := {expr}; END_IF"
                        else:
                            piece = f"{target} := {expr}"
                    else:
                        piece = f"{target} := {expr}" if target else expr
                else:
                    piece = str(stmt).strip()
                if piece:
                    if not piece.endswith(";"):
                        piece = f"{piece};"
                    lines.append(piece)
            for todo in net.get("unresolved_parts") or []:
                text = str(todo).strip()
                if text:
                    lines.append(f"(* TODO: {text} *)")
    if lines:
        return "\n".join(lines)
    stmts = _folded_logic_lines(job, block_name)
    out: list[str] = []
    for raw in stmts:
        line = str(raw).strip()
        if line.startswith("[") and "]" in line:
            title, line = line[1:].split("]", 1)
            title = title.strip()
            line = line.strip()
            if title:
                out.append(f"// NETWORK: {title}")
        if line:
            if not line.endswith(";"):
                line = f"{line};"
            out.append(line)
    return "\n".join(out)


def _scl_from_ir_translator(job: dict[str, Any], block_name: str) -> str:
    """Reuse existing LAD/FBD→SCL translator when ingest skipped scl_sources."""
    try:
        from agents.plc.tia.flgnet_fold import attach_folded
        from agents.plc.tia.ir import PlcProject
        from agents.plc.tia.scl import translate_block_to_scl
        from agents.plc.tia.scl_rewrite import _load_ir_blocks, refuse_body_write_reason
    except Exception:  # noqa: BLE001
        return ""
    try:
        ir_blocks = _load_ir_blocks(job)
    except Exception:  # noqa: BLE001
        return ""
    block = ir_blocks.get(block_name)
    if block is None:
        return ""
    if refuse_body_write_reason(block):
        # Still try translate when networks exist — chat dump, not writeback.
        if not getattr(block, "networks", None) and not str(getattr(block, "source_text", "") or "").strip():
            return ""
    try:
        project = PlcProject(name=str(job.get("project_name") or "job"))
        project.add_block(block)
        attach_folded(project)
        block = project.blocks.get(block_name) or block
    except Exception:  # noqa: BLE001
        pass
    try:
        return str(translate_block_to_scl(block) or "").strip()
    except Exception:  # noqa: BLE001
        logger.warning("IR SCL translate failed for %s", block_name, exc_info=True)
        return ""


def _scl_from_export_package(job: dict[str, Any], block_name: str) -> str:
    export_dir = str(job.get("export_dir") or "").strip()
    if not export_dir:
        return ""
    try:
        from agents.plc.tia.package import _safe_filename
    except Exception:  # noqa: BLE001
        def _safe_filename(name: str) -> str:  # type: ignore[misc]
            return re.sub(r'[\\/:*?"<>|]', "_", name)

    path = Path(export_dir) / "converted_scl" / f"{_safe_filename(block_name)}.scl"
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return ""


def _resolve_block_scl_text(job: dict[str, Any], block_name: str) -> tuple[str, str | None]:
    """SCL unit for chat: scl_sources → IR translator → package → folded dump.

    Second value is a one-line 程序体不可用 reason when the body is missing/TODO-only.
    """
    from agents.plc.tia.scl_rewrite import scl_is_untranslated

    stored = str((job.get("scl_sources") or {}).get(block_name) or "").strip()
    if stored:
        reason = "程序体不可用（仅 TODO / 占位）" if scl_is_untranslated(stored) else None
        return stored, reason

    ir_scl = _scl_from_ir_translator(job, block_name)
    if ir_scl:
        reason = "程序体不可用（仅 TODO / 占位）" if scl_is_untranslated(ir_scl) else None
        return ir_scl, reason

    pkg = _scl_from_export_package(job, block_name)
    if pkg:
        reason = "程序体不可用（仅 TODO / 占位）" if scl_is_untranslated(pkg) else None
        return pkg, reason

    folded = _folded_scl_dump(job, block_name).strip()
    meta = _block_meta(job, block_name)
    if folded:
        # Body excerpt exists even though ingest did not store a compilation unit.
        return folded, None
    return "(* 无已导出程序体 / 无折叠语句 *)", _program_body_unavailable_reason(meta)


def _format_block_scl_markdown(job: dict[str, Any], block_name: str) -> list[str]:
    """Full SCL fence — never an empty card after the title."""
    scl, reason = _resolve_block_scl_text(job, block_name)
    title = f"完整 SCL：{reason}" if reason else "完整 SCL："
    body = (scl or "(* 无已导出程序体 / 无折叠语句 *)").splitlines() or ["(* 无已导出程序体 / 无折叠语句 *)"]
    return [title, "```scl", *body, "```"]
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
    lines = ["**优化提示**" + (f"（`{block_name}`）" if block_name else "（工程）")]
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
            "NESTED_FB_TYPE": "审查块内多实例成员类型；这不是父 FB CALL 子 FB。",
            "MULTI_INSTANCE_CHAIN": "记录嵌套链；勿为改数字扁平化多实例。不可写体则只出 HITL 计划。",
        }.get(code, "结合调用与 IO 再确认是否可简化。")
        lines.append(f"- [{sev}] {msg} → {tip}")
        actionable += 1
        if actionable >= 5:
            break
    if not actionable:
        lines.append("- 未发现 warn/risk 级发现；可点「优化提案」做逻辑级改写预览。")
    return lines

def _join_capped(items: list[str], *, limit: int = 6) -> str:
    if not items:
        return "—"
    shown = items[:limit]
    more = f" 等{len(items)}个" if len(items) > limit else ""
    return ", ".join(shown) + more

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

    assoc = _block_assoc_lines(job, block_name)
    for line in assoc:
        if line.startswith("使用") or line.startswith("被使用"):
            lines.append(line)

    nest_line = None if include_full_scl else _format_nested_fb_line(job, block_name)
    if nest_line:
        lines.append(nest_line)

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
        if include_full_scl:
            lines.extend(_format_block_scl_markdown(job, block_name))
            lines.extend(
                _format_typed_as_nest_lines(job, block_name, compact=False, always=False)
            )
    elif include_full_scl:
        lines.extend(_format_block_scl_markdown(job, block_name))
        lines.extend(
            _format_typed_as_nest_lines(job, block_name, compact=False, always=False)
        )
    elif (job.get("scl_sources") or {}).get(block_name):
        lines.append("_下一步：说「展开 SCL」看完整源码；或问「谁读写这些信号」/「优化建议」。_")
    else:
        lines.append("_下一步：可选中画布查看信号子图；或问「优化建议」。_")
    return lines

def _format_block_runtime_explain(
    job: dict[str, Any],
    block_name: str,
    block: dict[str, Any],
    *,
    through_member: str | None = None,
    nest_block: str | None = None,
) -> list[str]:
    """分析 / 这个块干什么 / 运行逻辑：role, IO, CALLS, 网络步序, folded SCL, 全链."""
    comment = str(block.get("comment") or "").strip()
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
            for ln in str(scl).splitlines()
            if (":=" in ln or "=>" in ln or "(" in ln)
            and not ln.strip().startswith("//")
            and not ln.strip().startswith("(*")
            and not ln.strip().upper().startswith("NETWORK")
            and "VAR" not in ln.upper().split()[:1]
        ][:16]
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
        lines.append(f"理解：{understanding}")
        lines.append(f"作用：{_purpose_from_fold(folded, reads, writes)}")

    lines.append(f"输入：{_join_capped(reads) if reads else '（无已验证读取）'}")
    lines.append(f"输出：{_join_capped(writes) if writes else '（无已验证写入）'}")
    if iface_inout and not (set(iface_inout) <= set(reads) & set(writes)):
        lines.append(f"InOut：{_join_capped(iface_inout, limit=4)}")

    call_bits: list[str] = []
    if callers:
        call_bits.append("被调用：" + _join_capped(callers, limit=8))
    if callees:
        call_bits.append("调用：" + _join_capped(callees, limit=8))
    if call_bits:
        lines.append("；".join(call_bits))
    for line in _block_assoc_lines(job, block_name):
        if line.startswith("使用") or line.startswith("被使用"):
            if line not in lines:
                lines.append(line)

    if titles:
        lines.append("逻辑：" + " → ".join(titles[:16]))
        lines.append("运行步骤：" + " → ".join(titles[:16]))
    if not (interface_only or (protected and not body_available)):
        lines.extend(_format_scl_logic_block(folded))
    else:
        lines.append("程序体：不可用（未解密 / 未导出）")

    lines.extend(
        _format_typed_as_nest_lines(
            job,
            nest_block or block_name,
            through_member=through_member,
            compact=False,
            always=True,
        )
    )
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

def _typed_as_nest_payload(
    job: dict[str, Any],
    block_name: str,
    *,
    through_member: str | None = None,
) -> dict[str, Any]:
    """Full TYPED_AS chains + STAT member names for a block (or one member)."""
    from agents.plc.tia.typed_as import (
        format_chain,
        nest_depth_of,
        typed_as_chains,
        typed_as_members,
    )

    kg = job.get("knowledge_graph") or {}
    depth = nest_depth_of(kg, block_name)
    members = typed_as_members(kg, block_name)
    if through_member:
        want = through_member.strip().lstrip("#")
        want_l = want.lower()
        members = [
            m
            for m in members
            if str(m.get("member") or "").strip().lstrip("#").lower() == want_l
        ]
    member_bits: list[str] = []
    chain_lines: list[str] = []
    child_types = {str(item.get("type_block") or "") for item in members if item.get("type_block")}
    for item in members:
        member = str(item.get("member") or "?")
        child = str(item.get("type_block") or "")
        if not child:
            continue
        rest = typed_as_chains(kg, child)
        if rest:
            for path in rest:
                tail = " → ".join(f"`{n}`" for n in path[1:] if n)
                bit = f"`{block_name}.{member} : {child}`"
                member_bits.append(f"{bit} → {tail}" if tail else bit)
        else:
            member_bits.append(f"`{block_name}.{member} : {child}`")
    for path in typed_as_chains(kg, block_name):
        if through_member:
            if not child_types or len(path) < 2 or path[1] not in child_types:
                continue
        rendered = format_chain(path)
        if rendered:
            chain_lines.append(rendered)
    # De-dupe while preserving order
    member_bits = list(dict.fromkeys(member_bits))
    chain_lines = list(dict.fromkeys(chain_lines))
    return {
        "depth": depth,
        "members": member_bits,
        "chains": chain_lines,
        "has_nest": bool(member_bits or chain_lines or depth),
    }

def _format_typed_as_nest_lines(
    job: dict[str, Any],
    block_name: str,
    *,
    through_member: str | None = None,
    compact: bool = False,
    always: bool = False,
) -> list[str]:
    """Engineer-facing nest listing. ``always`` prints 无 FB-as-type when depth 0."""
    payload = _typed_as_nest_payload(job, block_name, through_member=through_member)
    depth = int(payload.get("depth") or 0)
    members = list(payload.get("members") or [])
    chains = list(payload.get("chains") or [])
    if not members and not chains:
        if always:
            who = f"`{block_name}`"
            if through_member:
                who = f"`{block_name}.{through_member}`"
            return [f"{who} 无 FB-as-type 嵌套（STAT 成员类型不是另一个 FB）"]
        return []
    if compact:
        bits = members or chains
        # Card keeps the existing ``Child : FB_B`` shape plus remaining types.
        short: list[str] = []
        for bit in bits:
            short.append(bit.replace(f"{block_name}.", "", 1) if bit.startswith(f"`{block_name}.") else bit)
        return [f"嵌套 FB 类型（深度 {depth}）：" + "；".join(short[:6])]
    lines = [f"**FB-as-type 嵌套链**（`{block_name}`，深度 {depth}）"]
    if through_member:
        lines[0] += f" · 经成员 `{through_member}`"
    if members:
        lines.append("成员：")
        for bit in members:
            lines.append(f"- {bit}")
    if chains:
        lines.append("链：")
        for chain in chains:
            lines.append(f"- {chain}")
    return lines

def _format_nested_fb_line(job: dict[str, Any], block_name: str) -> str | None:
    """Node-card line: full TYPED_AS path, not one embed level only."""
    lines = _format_typed_as_nest_lines(job, block_name, compact=True)
    return lines[0] if lines else None
