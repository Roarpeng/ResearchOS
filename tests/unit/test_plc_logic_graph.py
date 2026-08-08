"""Logic graph reduction: CALLS / USES + DEPENDS_ON derived from tag refs."""

from __future__ import annotations

from gateway.app.services.plc_jobs import _logic_graph_from_kg, refresh_logic_graph


def test_logic_graph_prefers_calls_over_depends_on():
    kg = {
        "nodes": [
            {"id": "Block::FB1", "type": "Block", "props": {"name": "FB1", "block_type": "FB"}},
            {"id": "Block::DB10", "type": "Block", "props": {"name": "DB10", "block_type": "DB"}},
            {"id": "Project::P", "type": "Project", "props": {"name": "P"}},
            {"id": "Tag::DB10.Run", "type": "Tag", "props": {"name": "DB10.Run"}},
        ],
        "edges": [
            {"source": "Project::P", "target": "Block::FB1", "type": "CONTAINS"},
            {"source": "Project::P", "target": "Block::DB10", "type": "CONTAINS"},
            {"source": "Block::FB1", "target": "Tag::DB10.Run", "type": "READS"},
            {"source": "Block::FB1", "target": "Tag::DB10.Run", "type": "WRITES"},
            {"source": "Block::FB1", "target": "Block::DB10", "type": "CALLS"},
        ],
    }
    lg = _logic_graph_from_kg(kg)
    types = {e["type"] for e in lg["edges"]}
    assert "CONTAINS" not in types
    assert "CALLS" in types
    # Stronger CALLS already links the pair — no redundant DEPENDS_ON
    assert "DEPENDS_ON" not in types


def test_logic_graph_derives_depends_on_from_reads_without_uses():
    kg = {
        "nodes": [
            {"id": "Block::FB1", "type": "Block", "props": {"name": "FB1", "block_type": "FB"}},
            {"id": "Block::DB10", "type": "Block", "props": {"name": "DB10", "block_type": "DB"}},
            {"id": "Tag::DB10.Run", "type": "Tag", "props": {"name": "DB10.Run"}},
        ],
        "edges": [
            {"source": "Block::FB1", "target": "Tag::DB10.Run", "type": "READS"},
            {"source": "Block::FB1", "target": "Tag::DB10.Run", "type": "WRITES"},
        ],
    }
    lg = _logic_graph_from_kg(kg)
    deps = [e for e in lg["edges"] if e["type"] == "DEPENDS_ON"]
    assert deps[0]["source"] == "Block::FB1"
    assert deps[0]["target"] == "Block::DB10"
    assert deps[0]["weight"] == 2


def test_refresh_logic_graph_updates_job():
    job = {
        "knowledge_graph": {
            "nodes": [
                {"id": "Block::A", "type": "Block", "props": {"name": "A"}},
                {"id": "Block::B_DB", "type": "Block", "props": {"name": "B_DB"}},
            ],
            "edges": [
                {"source": "Block::A", "target": "Tag::B_DB.x", "type": "READS"},
            ],
        },
        "logic_graph": {"nodes": [], "edges": [{"type": "CONTAINS"}]},
    }
    refresh_logic_graph(job)
    assert any(e["type"] == "DEPENDS_ON" for e in job["logic_graph"]["edges"])
    assert not any(e["type"] == "CONTAINS" for e in job["logic_graph"]["edges"])
