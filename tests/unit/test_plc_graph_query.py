"""Deterministic PLC knowledge-graph query coverage."""

from __future__ import annotations

from agents.plc.tia.graph_query import (
    callees_of,
    callers_of,
    dead_blocks,
    derive_depends_on_edges,
    query,
    reachable_from,
    readers_of_tag,
    writers_of_tag,
)


def _kg() -> dict:
    return {
        "nodes": [
            {"id": "Block::OB1", "type": "Block", "props": {"name": "OB1", "block_type": "OB"}},
            {"id": "Block::FB_A", "type": "Block", "props": {"name": "FB_A", "block_type": "FB"}},
            {"id": "Block::FB_B", "type": "Block", "props": {"name": "FB_B", "block_type": "FB"}},
            {"id": "Block::FB_orphan", "type": "Block", "props": {"name": "FB_orphan", "block_type": "FB"}},
            {"id": "Tag::MotorRun", "type": "Tag", "props": {"name": "MotorRun"}},
        ],
        "edges": [
            {"source": "Block::OB1", "target": "Block::FB_A", "type": "CALLS"},
            {"source": "Block::FB_A", "target": "Block::FB_B", "type": "CALLS"},
            {"source": "Block::FB_A", "target": "Tag::MotorRun", "type": "WRITES"},
            {"source": "Block::FB_B", "target": "Tag::MotorRun", "type": "READS"},
        ],
    }


def test_block_call_and_tag_access_queries():
    kg = _kg()

    assert callers_of(kg, "FB_A") == ["OB1"]
    assert callees_of(kg, "FB_A") == ["FB_B"]
    assert writers_of_tag(kg, "MotorRun") == ["FB_A"]
    assert readers_of_tag(kg, "MotorRun") == ["FB_B"]


def test_reachability_and_dead_blocks_from_ob():
    kg = _kg()

    assert reachable_from(kg) == {"OB1", "FB_A", "FB_B"}
    assert dead_blocks(kg) == ["FB_orphan"]


def test_depends_on_uses_shared_tag_evidence():
    deps = derive_depends_on_edges(_kg())

    assert {
        "source": "Block::FB_A",
        "target": "Block::FB_B",
        "type": "DEPENDS_ON",
        "weight": 1,
        "evidence": "shared_tag:MotorRun",
    } in deps


def test_query_returns_source_edge_evidence():
    result = query(_kg(), "writers", tag="MotorRun")

    assert result["op"] == "writers"
    assert result["result"] == ["FB_A"]
    assert result["evidence"] == [
        {"source": "Block::FB_A", "target": "Tag::MotorRun", "type": "WRITES"}
    ]


def test_depends_query_returns_access_evidence_not_derived_edges():
    result = query(_kg(), "depends", block_name="FB_A", target_block="FB_B")

    assert result["result"]["depends"] is True
    assert {edge["type"] for edge in result["evidence"]} == {"WRITES", "READS"}
