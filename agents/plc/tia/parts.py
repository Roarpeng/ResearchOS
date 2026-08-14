"""Canonical Siemens LAD/FBD Part names used by fold / SCL / KG."""

from __future__ import annotations

from agents.plc.tia.ir import Part

# Openness exports mix IEC names (CTU) and LAD box names (CtU).
PART_ALIASES: dict[str, str] = {
    "CtU": "CTU",
    "CtD": "CTD",
    "CtUD": "CTUD",
    "CTU": "CTU",
    "CTD": "CTD",
    "CTUD": "CTUD",
    "SetCoil": "Set",
    "ResetCoil": "Reset",
    "SCoil": "Set",
    "RCoil": "Reset",
    "Set": "Set",
    "Reset": "Reset",
    "TONR": "TONR",
    "TON_R": "TONR",
    "Conv": "Convert",
    "Convert": "Convert",
    "Round": "Round",
    "Mux": "Mux",
    "Demux": "Demux",
    "JumpUnconditional": "Jump",
    "Jump": "Jump",
    "Label": "Label",
    "Ret": "Return",
    "Return": "Return",
    "SR": "SR",
    "RS": "RS",
}

COMPARE_OPS = {
    "Eq": "=",
    "Ne": "<>",
    "Gt": ">",
    "Ge": ">=",
    "Lt": "<",
    "Le": "<=",
}

CONTACT_PARTS = {"Contact", "NegContact", "NotContact", "ContactNeg"}
COIL_PARTS = {"Coil", "NegCoil", "Set", "Reset", "Save"}
MOVE_PARTS = {"Move", "Assign", "Move_Bool", "Move_Word", "Move_DWord", "Move_Real"}
COUNTER_PARTS = {"CTU", "CTD", "CTUD"}
TIMER_PARTS = {"TON", "TOF", "TP", "TONR"}
EDGE_TRIG_PARTS = {"R_TRIG", "F_TRIG", "P_TRIG"}
LATCH_PARTS = {"SR", "RS"}
CONVERT_PARTS = {"Convert", "Round"}
MUX_PARTS = {"Mux", "Demux"}
JUMP_PARTS = {"Jump", "Label", "Return"}
CALL_PARTS = {"Call", "CallPart"}
BOX_PARTS = COUNTER_PARTS | TIMER_PARTS | EDGE_TRIG_PARTS | LATCH_PARTS
BRANCH_PARTS = CONTACT_PARTS | set(COMPARE_OPS)


def canon_part(name: str) -> str:
    key = (name or "").strip()
    if not key:
        return ""
    if key in PART_ALIASES:
        return PART_ALIASES[key]
    return PART_ALIASES.get(key.upper(), key)


def format_todo(part: Part) -> str:
    """Structured leftover: never silent-drop; always name the Siemens Part."""
    pins: list[str] = []
    for pin, acc in (part.accesses or {}).items():
        pins.append(f"{pin}={acc.as_scl()}")
    templates = [f"{k}={v}" for k, v in (part.template_values or {}).items() if not str(k).startswith("__")]
    pin_txt = ",".join(pins) if pins else "-"
    tpl_txt = ",".join(templates) if templates else "-"
    return (
        f"(* TODO[{part.name or 'unknown'}] uid={part.uuid or '-'} "
        f"pins={{{pin_txt}}} templates={{{tpl_txt}}} *)"
    )
