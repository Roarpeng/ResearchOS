"""Motion + Failure Analysis agents — read-only KG projections.

Builds the project knowledge graph from the ``tia_openness_surface`` fixture
(same path as ``test_plc_device_kg.py``), enriches it with a minimal motion/
failure control chain, then runs both agents on a minimal ``TaskState`` and
asserts their structured outputs cite only real graph edges.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.failure import run as failure_run
from agents.motion import run as motion_run
from agents.plc.tia.kg import build_knowledge_graph
from agents.plc.tia.simaticml import extract_project
from agents.registry import get_agent_registry
from runtime.researchos_runtime.state import initial_state

SURFACE = Path(__file__).resolve().parents[1] / "fixtures" / "tia_openness_surface"


def _node(node_id: str, node_type: str, **props: str) -> dict:
    return {"id": node_id, "type": node_type, "props": props}


def _edge(source: str, target: str, etype: str, **props: str) -> dict:
    return {"source": source, "target": target, "type": etype, "props": props}


@pytest.fixture(scope="module")
def enriched_kg():
    project = extract_project(SURFACE, project_name="OpennessSurface")
    data = build_knowledge_graph(project).to_json()
    # Minimal motion/failure control chain on top of the device-layer fixture:
    #   FB_Axis writes Axis_1 (symptom); Main calls FB_Axis; FB_Axis calls
    #   FC_ServoCmd and reads ServoEnable, written upstream by FB_SafetyDoor.
    data["nodes"].extend(
        [
            _node("Block::FB_Axis", "Block", name="FB_Axis", block_type="FB"),
            _node("Block::FC_ServoCmd", "Block", name="FC_ServoCmd", block_type="FC"),
            _node("Block::FB_SafetyDoor", "Block", name="FB_SafetyDoor", block_type="FB"),
            _node("Tag::Axis_1", "Tag", name="Axis_1"),
            _node("Tag::ServoEnable", "Tag", name="ServoEnable"),
        ]
    )
    data["edges"].extend(
        [
            _edge("Block::FB_Axis", "Tag::Axis_1", "WRITES", network="N1"),
            _edge("Block::Main", "Block::FB_Axis", "CALLS"),
            _edge("Block::FB_Axis", "Block::FC_ServoCmd", "CALLS"),
            _edge("Block::FB_Axis", "Tag::ServoEnable", "READS"),
            _edge("Block::FB_SafetyDoor", "Tag::ServoEnable", "WRITES"),
        ]
    )
    return data


def _interlock_finding() -> dict:
    return {
        "code": "OUTPUT_NO_INTERLOCK",
        "severity": "warn",
        "message": "`FB_Axis` 输出 `Axis_1` 未见明显互锁触点（仅单条件）。",
        "evidence": [
            {"kind": "folded_logic", "block": "FB_Axis", "network": "N1", "target": "Axis_1"}
        ],
    }


def _make_state(enriched_kg: dict, *, symptom: str = "Axis_1") -> dict:
    state = initial_state("tsk_motion_failure", "轴 Axis_1 回零失败")
    state["meta"] = {
        "plc_tia_analysis": {
            "knowledge_graph": enriched_kg,
            "analyst_findings": [_interlock_finding()],
        },
        "failure_symptom": symptom,
    }
    return state


def _real_edge_triples(kg: dict) -> set[tuple[str, str, str]]:
    return {
        (str(e["source"]), str(e["target"]), str(e["type"])) for e in kg["edges"]
    }


def test_motion_view_from_fixture_kg(enriched_kg):
    out = motion_run(_make_state(enriched_kg))
    view = out["meta"]["motion_view"]

    assert view["status"] == "ok"
    assert view["readonly"] is True
    assert len(view["axes"]) == 1

    axis = view["axes"][0]
    assert axis["axis"] == "Axis_1"
    assert axis["kind"] == "axis"
    assert axis["device"] == "PLC_1"
    assert axis["writers_blocks"] == ["FB_Axis"]

    # Writers must be real WRITES edges from the KG.
    assert len(axis["writers"]) == 1
    real = _real_edge_triples(enriched_kg)
    for writer_edge in axis["writers"]:
        assert (
            writer_edge["source"],
            writer_edge["target"],
            writer_edge["type"],
        ) in real

    # Interlock finding (OUTPUT_NO_INTERLOCK) is referenced for the writer block.
    assert len(axis["interlocks"]) == 1
    assert axis["interlocks"][0]["code"] == "OUTPUT_NO_INTERLOCK"

    assert any(t["tool"] == "motion.kg.view" for t in out["tool_traces"])
    assert any(e["type"] == "motion.completed" for e in out["events"])


def test_failure_analysis_from_fixture_kg(enriched_kg):
    out = failure_run(_make_state(enriched_kg))
    analysis = out["meta"]["failure_analysis"]

    assert analysis["status"] == "ok"
    assert analysis["readonly"] is True
    assert analysis["symptom"] == "Axis_1"
    assert analysis["symptom_source"] == "meta.failure_symptom"

    candidates = analysis["candidates"]
    assert candidates, "expected at least one root-cause candidate"
    assert analysis["evidence"], "expected non-empty evidence edges"

    real = _real_edge_triples(enriched_kg)
    for cand in candidates:
        assert cand["supporting_edges"], "candidate must cite real edges"
        assert 0 < cand["depth"] <= 3
        assert 0.0 < cand["confidence"] <= 1.0
        for edge in cand["supporting_edges"]:
            assert (
                edge["source"],
                edge["target"],
                edge["type"],
            ) in real, "hypothesis cites a fabricated edge"

    # Direct writer is the depth-1 candidate; upstream chain reaches depth-3.
    by_name = {cand["node"]["name"]: cand for cand in candidates}
    assert by_name["FB_Axis"]["depth"] == 1
    assert by_name["FB_SafetyDoor"]["depth"] == 3

    assert any(t["tool"] == "failure.kg.trace" for t in out["tool_traces"])
    assert any(e["type"] == "failure.completed" for e in out["events"])


def test_failure_symptom_falls_back_to_query(enriched_kg):
    state = _make_state(enriched_kg)
    del state["meta"]["failure_symptom"]
    out = failure_run(state)
    analysis = out["meta"]["failure_analysis"]
    assert analysis["symptom"] == "Axis_1"
    assert analysis["symptom_source"] == "goal.raw_query"
    assert analysis["candidates"]


def test_no_data_safe_results():
    state = initial_state("tsk_no_data", "motion without any PLC project")
    motion = motion_run(state)
    assert motion["meta"]["motion_view"]["status"] == "no_data"
    assert motion["meta"]["motion_readonly"] is True

    failure = failure_run(state)
    assert failure["meta"]["failure_analysis"]["status"] == "no_data"
    assert failure["meta"]["failure_readonly"] is True


def test_registry_contains_motion_and_failure():
    reg = get_agent_registry()
    assert "motion" in reg
    assert "failure" in reg
    assert callable(reg["motion"]) and callable(reg["failure"])
