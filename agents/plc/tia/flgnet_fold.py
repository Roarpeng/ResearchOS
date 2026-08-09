"""Fold SimaticML FlgNet wire graphs into reusable PLC expression IR."""

from __future__ import annotations

from agents.plc.tia.ir import (
    Access,
    AccessScope,
    And,
    AssignStmt,
    Block,
    Compare,
    Expr,
    FoldedNetwork,
    Lit,
    Network,
    Not,
    Or,
    Part,
    PlcProject,
    Ref,
)

COMPARE_OPS = {
    "Eq": "=",
    "Ne": "<>",
    "Gt": ">",
    "Ge": ">=",
    "Lt": "<",
    "Le": "<=",
}

RLO_OUTPUT_PARTS = {"Contact", "NegContact", "NotContact", "ContactNeg"} | set(COMPARE_OPS)
BRANCH_PARTS = {"Contact", "NegContact", "NotContact", "ContactNeg", *COMPARE_OPS}
COIL_PARTS = {"Coil", "NegCoil", "Set", "Reset", "Save"}
MOVE_PARTS = {"Move", "Assign", "Move_Bool", "Move_Word", "Move_DWord", "Move_Real"}
COUNTER_PARTS = {"CTU", "CTD", "CTUD"}
TIMER_PARTS = {"TON", "TOF", "TP"}
EDGE_TRIG_PARTS = {"R_TRIG", "F_TRIG", "P_TRIG"}
CALL_PARTS = {"Call", "CallPart"}
BOX_PARTS = COUNTER_PARTS | TIMER_PARTS | EDGE_TRIG_PARTS
_SKIP_CALL_PINS = {"in", "operand", "db", "instance", "en", "eno", "EN", "ENO"}
_OUTPUT_SECTIONS = {"Output", "Return"}
_OUTPUT_PINS = {"Q", "QU", "QD", "OUT", "OUT1", "CV", "ET", "ENO", "RET_VAL"}


def _pin_assign_op(part: Part, pin: str) -> str:
    sec = str(part.template_values.get(f"__sec__{pin}") or "")
    if sec in _OUTPUT_SECTIONS or pin.upper() in _OUTPUT_PINS:
        return "=>"
    return ":="


def _paren(expr: str) -> str:
    """Parenthesize a term when it would bind ambiguously in a join."""
    return f"({expr})" if (" OR " in expr or " AND " in expr) else expr


def expr_to_scl(expr: Expr) -> str:
    """Render an expression with the same boolean parenthesis rules as SCL."""
    if isinstance(expr, Lit):
        if expr.value is True:
            return "TRUE"
        if expr.value is False:
            return "FALSE"
        return expr.value
    if isinstance(expr, Ref):
        return expr.access.as_scl()
    if isinstance(expr, Not):
        return f"NOT ({expr_to_scl(expr.operand)})"
    if isinstance(expr, And):
        return " AND ".join(_paren(expr_to_scl(item)) for item in expr.operands)
    if isinstance(expr, Or):
        return " OR ".join(_paren(expr_to_scl(item)) for item in expr.operands)
    if isinstance(expr, Compare):
        return f"({expr_to_scl(expr.lhs)} {expr.op} {expr_to_scl(expr.rhs)})"
    raise TypeError(f"Unsupported expression: {type(expr).__name__}")


def stmt_to_scl(stmt: AssignStmt) -> str:
    """Render a folded coil/move/call statement as SCL (prefer IF forms when clear)."""
    if stmt.kind == "call":
        return stmt.target_scl or "(* call *)"
    target = stmt.target.as_scl() if stmt.target is not None else stmt.target_scl or "(* coil target unknown *)"
    condition = expr_to_scl(stmt.value)
    if stmt.kind == "move":
        src = condition
        en = stmt.enable
        en_txt = expr_to_scl(en) if en is not None else "TRUE"
        if en is None or en_txt == "TRUE":
            return f"{target} := {src};"
        return f"IF {en_txt} THEN {target} := {src}; END_IF;"
    if stmt.kind == "neg_coil":
        return f"{target} := NOT ({condition});"
    if stmt.kind == "set":
        return f"{target} := TRUE;" if condition == "TRUE" else f"IF {condition} THEN {target} := TRUE; END_IF;"
    if stmt.kind == "reset":
        return f"{target} := FALSE;" if condition == "TRUE" else f"IF {condition} THEN {target} := FALSE; END_IF;"
    # Coil: simple boolean → IF/ELSE TRUE/FALSE (matches engineer mental model)
    if " AND " not in condition and " OR " not in condition and condition not in {"TRUE", "FALSE"}:
        return f"IF {condition} THEN {target} := TRUE; ELSE {target} := FALSE; END_IF;"
    return f"{target} := {condition};"


class _NetworkFolder:
    def __init__(self, network: Network) -> None:
        self.network = network
        self._visited: set[str] = set()

    def _find_wire_to_pin(self, uuid: str, pin: str):
        for wire in self.network.wires:
            for endpoint in wire.targets:
                if endpoint.kind == "namecon" and endpoint.uuid == uuid and endpoint.pin == pin:
                    return wire
        return None

    def _wires_to_pin(self, uuid: str, pin: str) -> list:
        return [
            wire
            for wire in self.network.wires
            for endpoint in wire.targets
            if endpoint.kind == "namecon" and endpoint.uuid == uuid and endpoint.pin == pin
        ]

    def _operand_access(self, part: Part) -> Access | None:
        wire = self._find_wire_to_pin(part.uuid, "operand")
        if wire and wire.source and wire.source.kind == "identcon":
            return self.network.access_parts.get(wire.source.uuid)
        return part.accesses.get("operand")

    def _pin_name_aliases(self, pin: str) -> tuple[str, ...]:
        """Siemens Move cardinality uses out1/out2… instead of out."""
        if pin == "out":
            return ("out", "out1", "OUT", "OUT1")
        return (pin,)

    def _access_bound_to_pin(self, part: Part, pin: str) -> Access | None:
        """Resolve Access on a part pin regardless of wire direction.

        Inputs: IdentCon → NameCon(pin)
        Outputs (Move CV etc.): NameCon(pin) → IdentCon
        """
        for wire in self.network.wires:
            for endpoint in wire.endpoints:
                if endpoint.kind != "namecon" or endpoint.uuid != part.uuid or endpoint.pin != pin:
                    continue
                for other in wire.endpoints:
                    if other.kind == "identcon":
                        return self.network.access_parts.get(other.uuid)
        return part.accesses.get(pin)

    def _pin_access(self, part: Part, pin: str) -> Access | None:
        for name in self._pin_name_aliases(pin):
            access = self._access_bound_to_pin(part, name)
            if access is not None:
                return access
        return None

    def _wire_driver_exprs(self, wire, sink: tuple[str, str] | None = None) -> list[Expr]:
        expressions: list[Expr] = []
        for endpoint in wire.endpoints:
            if sink and endpoint.kind == "namecon" and (endpoint.uuid, endpoint.pin) == sink:
                continue
            if endpoint.kind == "powerrail":
                expressions.append(Lit(True))
            elif endpoint.kind == "identcon":
                access = self.network.access_parts.get(endpoint.uuid)
                if access is not None:
                    expressions.append(Ref(access))
            elif endpoint.kind == "namecon" and endpoint.pin == "out":
                part = self.network.parts.get(endpoint.uuid)
                if part is not None and part.name in RLO_OUTPUT_PARTS:
                    expressions.append(self._part_out_expr(part))
        return expressions

    def _value_at_pin(self, uuid: str, pin: str) -> Expr:
        key = f"{uuid}.{pin}"
        if key in self._visited:
            return Lit("(* loop guard *)")
        self._visited.add(key)
        expressions = [
            expression
            for wire in self._wires_to_pin(uuid, pin)
            for expression in self._wire_driver_exprs(wire, sink=(uuid, pin))
        ]
        if not expressions:
            return Lit(True)
        return expressions[0] if len(expressions) == 1 else Or(tuple(expressions))

    def _part_out_expr(self, part: Part) -> Expr:
        if part.name in {"Contact", "NegContact", "NotContact", "ContactNeg"}:
            incoming = self._value_at_pin(part.uuid, "in")
            operand = self._operand_access(part)
            operand_expr: Expr = Ref(operand) if operand is not None else Lit("(* operand *)")
            if part.name in {"NegContact", "NotContact", "ContactNeg"} or part.negated:
                operand_expr = Not(operand_expr)
            return operand_expr if incoming == Lit(True) else And((incoming, operand_expr))
        if part.name in COMPARE_OPS:
            lhs = self._pin_access(part, "in1")
            rhs = self._pin_access(part, "in2")
            return Compare(
                COMPARE_OPS[part.name],
                Ref(lhs) if lhs is not None else Lit("(* in1 *)"),
                Ref(rhs) if rhs is not None else Lit("(* in2 *)"),
            )
        return Lit(f"(* out of {part.name or 'part'} not expressible *)")

    def fold(self) -> FoldedNetwork:
        folded = FoldedNetwork(network_id=self.network.id, title=self.network.title)
        if self.network.source_text:
            # SCL / StructuredText network: keep statements for folded_logic / chat
            for line in self.network.source_text.splitlines():
                text = line.strip()
                if not text:
                    continue
                if not text.endswith(";"):
                    text = f"{text};"
                folded.statements.append(
                    AssignStmt(None, Lit(True), kind="call", target_scl=text)
                )
            return folded
        for part in self.network.parts.values():
            if part.name in COIL_PARTS:
                target = self._operand_access(part)
                kind = {
                    "NegCoil": "neg_coil",
                    "Set": "set",
                    "Reset": "reset",
                }.get(part.name, "coil")
                folded.statements.append(AssignStmt(target, self._value_at_pin(part.uuid, "in"), kind))
            elif part.name in MOVE_PARTS or (part.name or "").startswith("Move"):
                src = self._pin_access(part, "in")
                dst = self._pin_access(part, "out")
                if dst is None:
                    dst = self._operand_access(part)
                src_expr: Expr = Ref(src) if src is not None else Lit("(* in *)")
                en_wires = self._wires_to_pin(part.uuid, "en")
                en_expr: Expr | None = None
                if en_wires:
                    drivers = [
                        e
                        for w in en_wires
                        for e in self._wire_driver_exprs(w, sink=(part.uuid, "en"))
                    ]
                    # Ignore pure powerrail enable (unconditional Move)
                    if drivers and drivers != [Lit(True)]:
                        en_expr = drivers[0] if len(drivers) == 1 else Or(tuple(drivers))
                folded.statements.append(
                    AssignStmt(dst, src_expr, kind="move", enable=en_expr)
                )
            elif part.name in BOX_PARTS:
                folded.statements.append(self._fold_box_call(part))
            elif (
                part.name in CALL_PARTS
                or part.template_values.get("Call")
                or part.template_values.get("calledBlock")
            ):
                folded.statements.append(self._fold_block_call(part))
            elif part.name in BRANCH_PARTS:
                continue
            else:
                folded.unresolved_parts.append(part.uuid or part.name or "unknown")
        return folded

    def _pin_has_real_driver(self, part: Part, pin: str) -> bool:
        """True when pin wire has a non-OpenCon driver (skip dangling R/LD etc.)."""
        for wire in self._wires_to_pin(part.uuid, pin):
            for endpoint in wire.endpoints:
                if endpoint.kind == "namecon" and endpoint.uuid == part.uuid and endpoint.pin == pin:
                    continue
                if endpoint.kind == "opencon":
                    continue
                return True
        return False

    def _fold_block_call(self, part: Part) -> AssignStmt:
        """Fold FC/FB Call parts into SCL call statements (wires + CallInfo params)."""
        called = (
            part.template_values.get("Call")
            or part.template_values.get("calledBlock")
            or ""
        ).strip().strip('"') or "UNKNOWN_BLOCK"
        instance = (
            part.accesses.get("instance")
            or part.accesses.get("Instance")
            or self._pin_access(part, "db")
        )
        params: list[str] = []
        seen_pins: set[str] = set()

        # 1) Explicit Access on CallInfo Parameter
        for pin, acc in part.accesses.items():
            if pin in _SKIP_CALL_PINS or pin in {"instance", "Instance"}:
                continue
            op = _pin_assign_op(part, pin)
            params.append(f"{pin} {op} {acc.as_scl()}")
            seen_pins.add(pin)

        # 2) FlgNet wires onto call pins
        for wire in self.network.wires:
            for ep in wire.endpoints:
                if ep.kind != "namecon" or ep.uuid != part.uuid:
                    continue
                pin = ep.pin or ""
                if not pin or pin in _SKIP_CALL_PINS or pin in seen_pins:
                    continue
                acc = None
                for other in wire.endpoints:
                    if other.kind == "identcon":
                        acc = self.network.access_parts.get(other.uuid)
                        if acc is not None:
                            break
                if acc is None:
                    continue
                op = _pin_assign_op(part, pin)
                params.append(f"{pin} {op} {acc.as_scl()}")
                seen_pins.add(pin)

        if instance is not None and instance.root:
            callee = (
                f"#{instance.root}"
                if instance.scope == AccessScope.LOCAL
                else f'"{instance.root}"'
            )
            # Siemens: multi-instance / InstanceDB → call the instance, not Type.method
            call = f"{callee}({', '.join(params)});"
        else:
            call = f"{called}({', '.join(params)});"
        return AssignStmt(None, Lit(True), kind="call", target_scl=call)

    def _fold_box_call(self, part: Part) -> AssignStmt:
        """Fold IEC counter/timer/edge boxes into a call-like SCL statement."""
        instance = part.accesses.get("instance")
        inst = instance.as_scl() if instance is not None else (
            f'"{part.template_values["InstanceDB"]}"'
            if part.template_values.get("InstanceDB")
            else part.name
        )
        params: list[str] = []
        # Boolean / RLO inputs may be driven by contacts, not IdentCon Access.
        for pin in ("CU", "CD", "R", "LD", "IN", "CLK"):
            if part.accesses.get(pin) is not None and not self._wires_to_pin(part.uuid, pin):
                params.append(f"{pin} := {part.accesses[pin].as_scl()}")
                continue
            if not self._pin_has_real_driver(part, pin):
                # Still allow explicit Access-bound pins (StatementList / CallInfo)
                access = part.accesses.get(pin)
                if access is not None:
                    params.append(f"{pin} := {access.as_scl()}")
                continue
            params.append(f"{pin} := {expr_to_scl(self._value_at_pin(part.uuid, pin))}")
        for pin in ("PV", "PT"):
            access = self._pin_access(part, pin) or part.accesses.get(pin)
            if access is not None:
                params.append(f"{pin} := {access.as_scl()}")
        for pin in ("CV", "Q", "QU", "QD", "ET"):
            access = self._pin_access(part, pin) or part.accesses.get(pin)
            if access is not None:
                params.append(f"{pin} => {access.as_scl()}")
        call = f"{inst}({', '.join(params)});"
        return AssignStmt(None, Lit(True), kind="call", target_scl=call)


def fold_network(network: Network) -> FoldedNetwork:
    """Fold one LAD/FBD network's FlgNet wires into expression statements."""
    return _NetworkFolder(network).fold()


def fold_block(block: Block) -> list[FoldedNetwork]:
    """Fold every network in a block."""
    return [fold_network(network) for network in block.networks]


def _expr_to_dict(expr: Expr) -> dict:
    if isinstance(expr, Lit):
        return {"type": "literal", "value": expr.value}
    if isinstance(expr, Ref):
        return {"type": "ref", "access": expr.access.as_scl()}
    if isinstance(expr, Not):
        return {"type": "not", "operand": _expr_to_dict(expr.operand)}
    if isinstance(expr, And):
        return {"type": "and", "operands": [_expr_to_dict(item) for item in expr.operands]}
    if isinstance(expr, Or):
        return {"type": "or", "operands": [_expr_to_dict(item) for item in expr.operands]}
    if isinstance(expr, Compare):
        return {
            "type": "compare",
            "op": expr.op,
            "lhs": _expr_to_dict(expr.lhs),
            "rhs": _expr_to_dict(expr.rhs),
        }
    raise TypeError(f"Unsupported expression: {type(expr).__name__}")


def folded_to_dict(folded: FoldedNetwork) -> dict:
    """Return a JSON-serializable representation of folded logic."""
    return {
        "network_id": folded.network_id,
        "title": folded.title,
        "statements": [
            {
                "target": statement.target.as_scl() if statement.target is not None else statement.target_scl,
                "kind": statement.kind,
                "value": _expr_to_dict(statement.value),
                **(
                    {"enable": _expr_to_dict(statement.enable)}
                    if statement.enable is not None
                    else {}
                ),
            }
            for statement in folded.statements
        ],
        "unresolved_parts": folded.unresolved_parts,
        "evidence": folded.evidence,
    }


def attach_folded(project: PlcProject) -> PlcProject:
    """Attach folded expressions to every project network and return the project."""
    for block in project.blocks.values():
        for network in block.networks:
            network.folded = fold_network(network)
    return project


def fold_project(project: PlcProject) -> dict[str, list[dict]]:
    """Return JSON-ready folded logic keyed by block name."""
    return {
        block.name: [folded_to_dict(network.folded or fold_network(network)) for network in block.networks]
        for block in project.blocks.values()
    }
