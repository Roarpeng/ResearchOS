"""SCL translator — PLC-IR blocks -> SCL source text.

Rule-based conversion with an LLM-ready fallback: LAD/FBD networks are
translated by walking the SimaticML wire graph (coils <- contacts <-
power rail); anything unresolvable is emitted as a structured TODO
comment so an LLM agent (or engineer) can finish it with full context.
"""

from __future__ import annotations

from agents.plc.tia.ir import (
    Access,
    AccessScope,
    Block,
    BlockType,
    InterfaceSection,
    Network,
    Part,
    PlcProject,
)

COMPARE_OPS = {
    "Eq": "=",
    "Ne": "<>",
    "Gt": ">",
    "Ge": ">=",
    "Lt": "<",
    "Le": "<=",
}

#: Parts whose "out" pin produces a boolean RLO that can drive a wire.
RLO_OUTPUT_PARTS = {"Contact", "NegContact", "NotContact", "ContactNeg"} | set(COMPARE_OPS)

#: Contact-like parts produce a boolean expression from their "in" pin.
BRANCH_PARTS = {"Contact", "NegContact", "NotContact", "Compare", "Eq", "Ne", "Gt", "Ge", "Lt", "Le"}


def _paren(expr: str) -> str:
    """Parenthesize a term when it would bind ambiguously in a join."""
    return f"({expr})" if (" OR " in expr or " AND " in expr) else expr

_SECTION_ORDER = [
    InterfaceSection.INPUT,
    InterfaceSection.OUTPUT,
    InterfaceSection.IN_OUT,
    InterfaceSection.STATIC,
    InterfaceSection.TEMP,
    InterfaceSection.CONSTANT,
]


class NetworkTranslator:
    """Translate one network's Parts+Wires into SCL statements."""

    def __init__(self, block: Block, network: Network) -> None:
        self.block = block
        self.network = network
        self.statements: list[str] = []
        self.notes: list[str] = []
        self._extra_decls: list[str] = []
        self._visited: set[str] = set()

    # -- wire helpers -------------------------------------------------------
    def _find_wire_to_pin(self, uuid: str, pin: str):
        for wire in self.network.wires:
            for ep in wire.targets:
                if ep.kind == "namecon" and ep.uuid == uuid and ep.pin == pin:
                    return wire
        return None

    def _wires_to_pin(self, uuid: str, pin: str) -> list:
        return [
            wire
            for wire in self.network.wires
            for ep in wire.targets
            if ep.kind == "namecon" and ep.uuid == uuid and ep.pin == pin
        ]

    def _operand_access(self, part: Part) -> Access | None:
        wire = self._find_wire_to_pin(part.uuid, "operand")
        if wire and wire.source and wire.source.kind == "identcon":
            return self.network.access_parts.get(wire.source.uuid)
        return part.accesses.get("operand")

    def _pin_access(self, part: Part, pin: str) -> Access | None:
        wire = self._find_wire_to_pin(part.uuid, pin)
        if wire and wire.source and wire.source.kind == "identcon":
            return self.network.access_parts.get(wire.source.uuid)
        return part.accesses.get(pin)

    # -- expression synthesis -------------------------------------------------
    def _wire_driver_exprs(self, wire, sink: tuple[str, str] | None = None) -> list[str]:
        """Boolean expressions driven onto a wire by its source-side endpoints.

        A wire is a net: powerrail drives TRUE, IdentCon drives its Access
        value, and the `out` pin of RLO-producing parts drives their value.
        """
        exprs: list[str] = []
        for ep in wire.endpoints:
            if sink and ep.kind == "namecon" and ep.uuid == sink[0] and ep.pin == sink[1]:
                continue
            if ep.kind == "powerrail":
                exprs.append("TRUE")
            elif ep.kind == "identcon":
                acc = self.network.access_parts.get(ep.uuid)
                if acc is not None:
                    exprs.append(acc.as_scl())
            elif ep.kind == "namecon" and ep.pin == "out":
                part = self.network.parts.get(ep.uuid)
                if part is not None and part.name in RLO_OUTPUT_PARTS:
                    exprs.append(self._part_out_expr(part))
        return exprs

    def _value_at_pin(self, uuid: str, pin: str) -> str:
        """Boolean value arriving at a part pin (multiple drivers -> OR)."""
        key = f"{uuid}.{pin}"
        if key in self._visited:
            return "(* loop guard *)"
        self._visited.add(key)
        exprs: list[str] = []
        for wire in self._wires_to_pin(uuid, pin):
            exprs.extend(self._wire_driver_exprs(wire, sink=(uuid, pin)))
        exprs = [e for e in exprs if e]
        if not exprs:
            return "TRUE"
        if len(exprs) == 1:
            return exprs[0]
        return " OR ".join(_paren(e) for e in exprs)

    def _part_out_expr(self, part: Part) -> str:
        name = part.name
        if name in {"Contact", "NegContact", "NotContact", "ContactNeg"}:
            # contact out = (in value) AND operand ; negated variants invert
            in_expr = self._value_at_pin(part.uuid, "in")
            operand = self._operand_access(part)
            op_expr = operand.as_scl() if operand else "(* operand *)"
            if name in {"NegContact", "NotContact", "ContactNeg"} or part.negated:
                op_expr = f"NOT ({op_expr})"
            if in_expr == "TRUE":
                return op_expr
            return f"{_paren(in_expr)} AND {_paren(op_expr)}"
        if name in COMPARE_OPS:
            in1 = self._pin_access(part, "in1")
            in2 = self._pin_access(part, "in2")
            op = COMPARE_OPS[name]
            lhs = in1.as_scl() if in1 else "(* in1 *)"
            rhs = in2.as_scl() if in2 else "(* in2 *)"
            return f"({lhs} {op} {rhs})"
        return f"(* out of {name or 'part'} not expressible *)"

    # -- statement emission ----------------------------------------------------
    def _emit_coil(self, part: Part) -> None:
        operand = self._operand_access(part)
        target = operand.as_scl() if operand else "(* coil target unknown *)"
        cond = self._value_at_pin(part.uuid, "in")
        if part.name == "NegCoil":
            self.statements.append(f"{target} := NOT ({cond});")
        elif part.name == "Set":
            if cond == "TRUE":
                self.statements.append(f"{target} := TRUE;")
            else:
                self.statements.append(f"IF {cond} THEN {target} := TRUE; END_IF;")
        elif part.name == "Reset":
            if cond == "TRUE":
                self.statements.append(f"{target} := FALSE;")
            else:
                self.statements.append(f"IF {cond} THEN {target} := FALSE; END_IF;")
        else:
            self.statements.append(f"{target} := {cond};")

    def _emit_move(self, part: Part) -> None:
        src = self._pin_access(part, "in")
        dst = self._pin_access(part, "out")
        if dst is None:
            dst = self._operand_access(part)
        src_txt = src.as_scl() if src else "(* in *)"
        dst_txt = dst.as_scl() if dst else "(* out *)"
        self.statements.append(f"{dst_txt} := {src_txt};")

    def _emit_call(self, part: Part) -> None:
        called = part.template_values.get("Call") or part.template_values.get("calledBlock") or ""
        called = called.strip().strip('"') or part.name
        instance = (
            part.accesses.get("instance")
            or part.accesses.get("Instance")
            or self._pin_access(part, "db")
        )
        params: list[str] = []
        for wire in self.network.wires:
            for ep in wire.targets:
                if ep.kind != "namecon" or ep.uuid != part.uuid:
                    continue
                if ep.pin in {"in", "operand", "db", "instance", "en", "eno"}:
                    continue
                acc = None
                if wire.source and wire.source.kind == "identcon":
                    acc = self.network.access_parts.get(wire.source.uuid)
                value = acc.as_scl() if acc else "(* signal *)"
                params.append(f"{ep.pin} := {value}")
        call = called or "UNKNOWN_BLOCK"
        if instance and instance.root:
            prefix = f"#{instance.root}" if instance.scope == AccessScope.LOCAL else f'"{instance.root}"'
            self.statements.append(f"{prefix}.{call}({', '.join(params)});")
        else:
            self.statements.append(f"{call}({', '.join(params)});")

    def translate(self) -> list[str]:
        """Return SCL statements for this network."""
        if self.network.source_text:
            return [line for line in self.network.source_text.splitlines() if line.strip()]

        for part in self.network.parts.values():
            name = part.name
            if name in {"Coil", "NegCoil", "Set", "Reset", "Save"}:
                self._emit_coil(part)
            elif name == "Move":
                self._emit_move(part)
            elif name in {"Call"} or "Call" in (part.template_values or {}):
                self._emit_call(part)
            elif name in BRANCH_PARTS:
                continue  # consumed by downstream coils
            else:
                self.statements.append(
                    f"(* TODO[{name or 'unknown'}]: instruction not auto-translated; "
                    f"translate from SimaticML Part UId={part.uuid} *)"
                )
        if not self.statements:
            self.statements.append("(* empty network *)")
        return self.statements


# ---------------------------------------------------------------------------
# Block / project level
# ---------------------------------------------------------------------------

def _header(block: Block) -> str:
    bt = block.block_type
    if bt == BlockType.UDT:
        return f"TYPE {block.name}"
    ret = ""
    if bt == BlockType.FC:
        returns = block.interface_section(InterfaceSection.RETURN)
        ret = f" : {returns[0].data_type or 'Void'}" if returns else " : Void"
    num = f"{block.number}" if block.number else "?"
    header = f"{bt.value} {block.name}{ret}"
    sub = []
    if block.number:
        sub.append(f"// Number: {bt.value}{num}")
    if block.programming_language:
        sub.append(f"// Original language: {block.programming_language}")
    if block.header_comment:
        sub.append(f"// {block.header_comment}")
    return header + ("\n" + "\n".join(sub) if sub else "")


def _interface_text(block: Block) -> str:
    if block.block_type in {BlockType.DB, BlockType.UDT}:
        lines = []
        for var in block.interface:
            comment = f"  // {var.comment}" if var.comment else ""
            value = f" := {var.start_value}" if var.start_value else ""
            lines.append(f"    {var.name} : {var.data_type or 'Struct'}{value};{comment}")
        return "\n".join(lines)

    lines = []
    for section in _SECTION_ORDER:
        members = block.interface_section(section)
        if not members:
            continue
        lines.append(f"VAR{section.value.upper()}")
        for var in members:
            if section == InterfaceSection.CONSTANT:
                val = var.start_value or "0"
                lines.append(f"    {var.name} : {var.data_type} := {val};")
            else:
                comment = f"  // {var.comment}" if var.comment else ""
                value = f" := {var.start_value}" if var.start_value else ""
                lines.append(f"    {var.name} : {var.data_type}{value};{comment}")
        lines.append("END_VAR")
    return "\n".join(lines)


def translate_block_to_scl(block: Block) -> str:
    """Convert one block to a full SCL compilation unit."""
    if block.block_type == BlockType.DB:
        body = _interface_text(block)
        return (
            f"DATA_BLOCK {block.name}\n"
            + (f"// Number: DB{block.number}\n" if block.number else "")
            + (f"NON_RETAIN\n" if not any(v.is_retain for v in block.interface) else "")
            + "STRUCT\n" + body + "\nEND_STRUCT;\nBEGIN\n\nEND_DATA_BLOCK"
        )
    if block.block_type == BlockType.UDT:
        return (
            f"TYPE {block.name}\nSTRUCT\n" + _interface_text(block) + "\nEND_STRUCT;\nEND_TYPE"
        )

    lines: list[str] = [_header(block)]
    interface = _interface_text(block)
    if interface:
        lines.append(interface)
    lines.append("BEGIN")

    for idx, network in enumerate(block.networks, start=1):
        title = network.title or f"Network {idx}"
        lines.append("")
        lines.append(f"// NETWORK {idx}: {title}")
        if network.comment:
            lines.append(f"// {network.comment}")
        translator = NetworkTranslator(block, network)
        for stmt in translator.translate():
            lines.append("    " + stmt)

    lines.append("")
    lines.append(f"END_{block.block_type.value}")
    return "\n".join(lines)


def convert_project_to_scl(project: PlcProject) -> dict[str, str]:
    """Map block name -> SCL source for every translatable block."""
    return {name: translate_block_to_scl(block) for name, block in project.blocks.items()}


def llm_prompt_for_network(block: Block, network: Network) -> str:
    """Context prompt for an LLM to translate a network the rules missed."""
    parts_txt = "\n".join(
        f"Part UId={p.uuid} Name={p.name} templates={p.template_values}"
        for p in network.parts.values()
    )
    wires_txt = "\n".join(
        f"Wire UId={w.uid}: {[(e.kind, e.uuid, e.pin) for e in w.endpoints]}"
        for w in network.wires
    )
    accesses_txt = "\n".join(
        f"Access UId={uid}: {acc.scope.value} {acc.root}.{'.'.join(acc.path)} ({acc.data_type})"
        for uid, acc in network.access_parts.items()
    )
    return (
        f"Translate the following TIA Portal network (block {block.name}, "
        f"language {network.programming_language or 'LAD'}) to equivalent SCL.\n"
        f"Network title: {network.title}\n\n"
        f"Parts:\n{parts_txt}\n\nAccesses:\n{accesses_txt}\n\nWires:\n{wires_txt}\n\n"
        "Return only SCL statements, preserving semantics (edges, timers, calls)."
    )
