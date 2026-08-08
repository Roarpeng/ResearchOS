"""Tests for FlgNet wire-graph folding into expression IR."""

from __future__ import annotations

import json
from pathlib import Path

from agents.plc.tia.flgnet_fold import (
    attach_folded,
    expr_to_scl,
    fold_project,
    stmt_to_scl,
)
from agents.plc.tia.scl import translate_block_to_scl
from agents.plc.tia.simaticml import extract_project

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "tia_exports"
CE_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "tia_ce"


def test_fb_motor_self_holding_fold_matches_scl() -> None:
    project = attach_folded(extract_project(FIXTURES, project_name="MotorDemo"))
    folded = project.blocks["FB_Motor"].networks[0].folded

    assert folded is not None
    assert len(folded.statements) == 1
    statement = folded.statements[0]
    assert statement.target is not None
    assert statement.target.name == "Running"
    assert expr_to_scl(statement.value) == (
        "((#Start OR #Running) AND NOT (#Stop)) AND NOT (#Fault)"
    )


def test_fold_project_is_json_serializable() -> None:
    project = attach_folded(extract_project(FIXTURES, project_name="MotorDemo"))
    payload = fold_project(project)

    json.dumps(payload)
    statement = payload["FB_Motor"][0]["statements"][0]
    assert statement["target"] == "#Running"
    assert statement["value"]["type"] == "and"


def test_ce_live_export_fold_move_out1_and_ctu() -> None:
    """Live CE: Clock→Tag coil; in1→out1; Gt+Move out1; Contact+CTU; empty."""
    project = attach_folded(extract_project(CE_FIXTURES, project_name="CeDemo"))
    assert "ce" in project.blocks
    block = project.blocks["ce"]
    assert len(block.networks) == 5

    n1, n2, n3, n4, n5 = [n.folded for n in block.networks]
    assert n1 is not None and n1.statements
    assert stmt_to_scl(n1.statements[0]) == (
        'IF "Clock_1Hz" THEN "Tag_1" := TRUE; ELSE "Tag_1" := FALSE; END_IF;'
    )

    assert n2 is not None and n2.statements
    assert stmt_to_scl(n2.statements[0]) == (
        "IF #in1 THEN #out1 := TRUE; ELSE #out1 := FALSE; END_IF;"
    )

    assert n3 is not None and n3.statements
    assert stmt_to_scl(n3.statements[0]) == "IF (#in2 > #in3) THEN #out2 := #in4; END_IF;"

    assert n4 is not None and n4.statements
    assert n4.unresolved_parts == []
    assert stmt_to_scl(n4.statements[0]) == (
        '"IEC_Counter_0_DB"(CU := #in5, PV := 1, CV => #out3);'
    )

    assert n5 is not None
    assert n5.statements == []

    scl = translate_block_to_scl(block)
    assert 'IF "Clock_1Hz" THEN "Tag_1" := TRUE; ELSE "Tag_1" := FALSE; END_IF;' in scl
    assert "IF #in1 THEN #out1 := TRUE; ELSE #out1 := FALSE; END_IF;" in scl
    assert "IF (#in2 > #in3) THEN #out2 := #in4; END_IF;" in scl
    assert '"IEC_Counter_0_DB"(CU := #in5, PV := 1, CV => #out3);' in scl
