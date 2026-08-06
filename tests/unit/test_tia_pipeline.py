"""End-to-end tests — TIA Openness export -> PLC-IR -> KG -> SCL pipeline.

Fixtures in tests/fixtures/tia_exports mimic a real Openness export of a
motor-control project (FB_Motor self-holding LAD, OB1 calling it, a
background instance DB and two tag tables).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.plc.tia import analyze_tia_exports
from agents.plc.tia.ir import BlockType
from agents.plc.tia.scl import llm_prompt_for_network
from agents.plc.tia.simaticml import parse_block_xml, parse_tag_table_xml

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "tia_exports"


@pytest.fixture(scope="module")
def result():
    return analyze_tia_exports(str(FIXTURES), project_name="MotorDemo")


# ---------------------------------------------------------------------------
# Extract: SimaticML -> PLC-IR
# ---------------------------------------------------------------------------

def test_extract_project_structure(result):
    project = result["project"]
    assert project.extraction_notes == []
    assert set(project.blocks) == {"FB_Motor", "Main", "MotorInst"}
    assert set(project.tag_tables) == {"HMI", "Safety"}
    assert project.summary() == {"FB": 1, "OB": 1, "DB": 1, "TagTables": 2, "Networks": 2}


def test_fb_motor_block_details(result):
    fb = result["project"].blocks["FB_Motor"]
    assert fb.block_type == BlockType.FB
    assert fb.number == 100
    assert fb.programming_language == "LAD"
    assert "self-holding" in fb.header_comment
    names = {v.name: v.section.value for v in fb.interface}
    assert names == {"Start": "Input", "Stop": "Input", "Fault": "Input", "Running": "Output"}
    assert len(fb.networks) == 1
    net = fb.networks[0]
    assert net.title == "Self-holding motor start"
    assert len(net.parts) == 5
    assert len(net.access_parts) == 5
    assert len(net.wires) == 9


def test_tag_tables_parsed(result):
    hmi = result["project"].tag_tables["HMI"]
    assert [t.name for t in hmi.tags] == ["StartCmd", "StopCmd"]
    assert hmi.tags[0].logical_address == "%I0.0"
    assert hmi.tags[0].comment == "HMI start pushbutton"
    safety = result["project"].tag_tables["Safety"]
    assert [t.name for t in safety.tags] == ["FaultOk"]


# ---------------------------------------------------------------------------
# Knowledge graph
# ---------------------------------------------------------------------------

def test_kg_calls_and_instance_edges(result):
    kg = result["knowledge_graph"]
    assert kg.callers_of("FB_Motor") == ["Main"]
    assert kg.callees_of("Main") == ["FB_Motor"]
    instance_edges = [
        e for e in kg.edges if e.type == "INSTANCE_OF"
    ]
    assert [(e.source, e.target) for e in instance_edges] == [
        ("Block::MotorInst", "Block::FB_Motor")
    ]


def test_kg_read_write_classification(result):
    kg = result["knowledge_graph"]
    assert kg.writers_of_tag("#Running") == ["FB_Motor"]
    assert kg.readers_of_tag("#Running") == ["FB_Motor"]
    assert kg.readers_of_tag("#Start") == ["FB_Motor"]
    assert kg.readers_of_tag("HMI.StartCmd") == ["Main"]
    # coil operands must never be classified as reads
    reads_running = [
        e for e in kg.edges if e.type == "READS" and e.target == "Tag::#Stop"
    ]
    assert [e.source for e in reads_running] == ["Block::FB_Motor"]


def test_kg_json_roundtrip(result):
    data = result["knowledge_graph"].to_json()
    assert {n["id"] for n in data["nodes"]} >= {
        "Project::MotorDemo",
        "Block::FB_Motor",
        "Block::Main",
        "Block::MotorInst",
        "TagTable::HMI",
        "Tag::StartCmd",
    }
    assert all({"source", "target", "type"} <= set(e) for e in data["edges"])


# ---------------------------------------------------------------------------
# SCL translation
# ---------------------------------------------------------------------------

def test_scl_self_holding_expression(result):
    scl = result["scl_sources"]["FB_Motor"]
    assert "#Running := ((#Start OR #Running) AND NOT (#Stop)) AND NOT (#Fault);" in scl
    assert "VARINPUT" in scl and "VAROUTPUT" in scl
    assert scl.startswith("FB FB_Motor")
    assert "END_FB" in scl


def test_scl_call_statement(result):
    scl = result["scl_sources"]["Main"]
    assert (
        '#MotorInst.FB_Motor(Start := "HMI".StartCmd, '
        'Stop := "HMI".StopCmd, Fault := "Safety".FaultOk);' in scl
    )
    assert "END_OB" in scl


def test_scl_db_instance(result):
    scl = result["scl_sources"]["MotorInst"]
    assert scl.startswith("DATA_BLOCK MotorInst")
    assert "Start : Bool;" in scl and "END_DATA_BLOCK" in scl


def test_llm_fallback_prompt_has_full_context(result):
    fb = result["project"].blocks["FB_Motor"]
    prompt = llm_prompt_for_network(fb, fb.networks[0])
    assert "FB_Motor" in prompt
    assert "Part UId=31" in prompt
    assert "Wire UId=41" in prompt
    assert "SCL" in prompt


# ---------------------------------------------------------------------------
# Direct parser entry points + CLI
# ---------------------------------------------------------------------------

def test_parse_block_xml_returns_none_for_tag_table():
    assert parse_block_xml(FIXTURES / "TagTables" / "HMI.xml") is None
    table = parse_tag_table_xml(FIXTURES / "Blocks" / "FB_Motor.xml")
    assert table is None


def test_cli_runs_end_to_end(tmp_path, capsys):
    from agents.plc.tia_cli import main

    code = main(
        [
            "--exports",
            str(FIXTURES),
            "--project-name",
            "MotorDemo",
            "--out",
            str(tmp_path / "scl"),
            "--kg",
            str(tmp_path / "kg.json"),
            "--json-summary",
        ]
    )
    assert code == 0
    captured = capsys.readouterr()
    assert "#Running := ((#Start OR #Running)" in captured.out
    assert (tmp_path / "scl" / "FB_Motor.scl").exists()
    assert (tmp_path / "scl" / "Main.scl").exists()
    assert (tmp_path / "kg.json").exists()


def test_cli_missing_dir_exits_nonzero():
    from agents.plc.tia_cli import main

    assert main(["--exports", str(FIXTURES.parent / "does_not_exist")]) == 2


def test_cli_empty_export_exits_nonzero(tmp_path):
    from agents.plc.tia_cli import main

    empty = tmp_path / "empty_exports"
    empty.mkdir()
    assert main(["--exports", str(empty)]) == 1
    assert main(["--exports", str(empty), "--allow-empty"]) == 0


def test_unrecognized_xml_is_noted(tmp_path):
    junk = tmp_path / "junk.xml"
    junk.write_text("<Root><DocumentType>Other.ML</DocumentType></Root>", encoding="utf-8")
    result = analyze_tia_exports(str(tmp_path))
    notes = " ".join(result["project"].extraction_notes)
    assert "unrecognized XML skipped" in notes
    assert "no PLC blocks or tag tables recognized" in notes


def test_missing_export_dir_reports_note():
    result = analyze_tia_exports(str(FIXTURES.parent / "does_not_exist"))
    assert result["project"].extraction_notes
    assert result["scl_sources"] == {}
