"""Unit tests — optimize proposal + XML comment patch + import bundle."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from agents.plc.tia.changeset import write_import_bundle
from agents.plc.tia.optimize import propose_optimization_changeset
from agents.plc.tia.xml_patch import match_xml_for_block, patch_block_header_comment

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "tia_exports"
FB_MOTOR_XML = FIXTURES / "Blocks" / "FB_Motor.xml"


def _job_with_dead() -> dict:
    return {
        "project_name": "OptDemo",
        "blocks": [
            {"name": "Main", "type": "OB", "number": 1, "networks": 1, "body_available": True},
            {
                "name": "FB_Motor",
                "type": "FB",
                "number": 100,
                "networks": 1,
                "body_available": True,
                "comment": "Motor",
            },
            {
                "name": "FB_orphan",
                "type": "FB",
                "number": 99,
                "networks": 0,
                "body_available": True,
            },
            {
                "name": "FB_Locked",
                "type": "FB",
                "number": 1000,
                "networks": 0,
                "interface_only": True,
                "body_available": False,
            },
        ],
        "knowledge_graph": {
            "nodes": [
                {"id": "Block::Main", "type": "Block", "props": {"name": "Main", "block_type": "OB"}},
                {
                    "id": "Block::FB_Motor",
                    "type": "Block",
                    "props": {"name": "FB_Motor", "block_type": "FB"},
                },
                {
                    "id": "Block::FB_orphan",
                    "type": "Block",
                    "props": {"name": "FB_orphan", "block_type": "FB"},
                },
                {
                    "id": "Block::FB_Locked",
                    "type": "Block",
                    "props": {
                        "name": "FB_Locked",
                        "block_type": "FB",
                        "interface_only": True,
                    },
                },
            ],
            "edges": [
                {
                    "source": "Block::Main",
                    "target": "Block::FB_Motor",
                    "type": "CALLS",
                    "props": {"evidence": "xml_call"},
                }
            ],
        },
        "source_xmls": [str(FB_MOTOR_XML)],
        "scl_sources": {},
        "folded_logic": {},
    }


def test_patch_block_header_comment(tmp_path: Path):
    dest = tmp_path / "FB_Motor.xml"
    patch_block_header_comment(FB_MOTOR_XML, "[OPT] patched comment", dest=dest)
    root = ET.parse(dest).getroot()
    texts = [
        (el.text or "")
        for el in root.iter()
        if el.tag.endswith("Text") or el.tag == "Text"
    ]
    assert any("[OPT] patched comment" in t for t in texts)


def test_match_xml_for_block():
    assert match_xml_for_block("FB_Motor", [FB_MOTOR_XML]) == FB_MOTOR_XML


def test_propose_optimization_marks_dead_and_skips_locked():
    job = _job_with_dead()
    cs = propose_optimization_changeset(job)
    assert cs.status == "proposed"
    kinds = {o.kind for o in cs.ops}
    assert "annotate" in kinds
    assert "set_block_comment" in kinds
    orphan_ops = [o for o in cs.ops if o.payload.get("block_name") == "FB_orphan"]
    assert orphan_ops
    # Locked: may annotate via dead list if unreachable — but must not stage XML for interface_only
    locked_stage = [
        o
        for o in cs.ops
        if o.kind == "stage_xml_import" and o.payload.get("block_name") == "FB_Locked"
    ]
    assert locked_stage == []
    assert any(str(n).startswith("optimize_plan:") for n in cs.notes)


def test_write_import_bundle_patches_comment_not_whole_pool(tmp_path: Path):
    job = _job_with_dead()
    # Only FB_Motor exists as XML; orphan has comment op without xml
    from agents.plc.tia.changeset import PlcChangeOp, PlcChangeSet

    cs = PlcChangeSet(
        id="t",
        ops=[
            PlcChangeOp(
                kind="set_block_comment",
                payload={"block_name": "FB_Motor", "comment": "[OPT] motor review"},
            )
        ],
        notes=["optimize_plan:# plan\n"],
    )
    other = tmp_path / "Other.xml"
    other.write_text("<Document><Name>Other</Name></Document>", encoding="utf-8")
    staged = write_import_bundle(
        tmp_path / "bundle",
        cs,
        [FB_MOTOR_XML, other],
    )
    assert len(staged) == 1
    assert staged[0].name == "FB_Motor.xml"
    text = staged[0].read_text(encoding="utf-8")
    assert "[OPT] motor review" in text
    assert (tmp_path / "bundle" / "optimize_plan.md").is_file()
