"""Evidence-gated PLC block cards for chat."""

from __future__ import annotations

from typing import Any

from .blocks import (
    _block_assoc_lines,
    _block_io_lists,
    _block_network_titles,
    _call_relation_names,
)
from .nested import _format_nested_fb_line, _format_typed_as_nest_lines
from .optimize import _block_risk_notes
from .scl import (
    _folded_logic_lines,
    _format_block_scl_markdown,
    _format_scl_logic_block,
    _purpose_from_fold,
)
from .shared import _join_capped

__all__ = [
    "_explain_block_understanding",
    "_describe_block_function",
    "_format_block_runtime_explain",
]


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
