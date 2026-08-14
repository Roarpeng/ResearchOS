"""PLC → Neo4j publish: nested maps must be flattened to primitives."""

from __future__ import annotations

import json

from agents.plc.tia.kg import PlcKnowledgeGraph
from agents.plc.tia.neo4j_publish import plc_kg_to_entities_relations, publish_plc_knowledge_graph
from knowledge.retrieval.graph import neo4j_safe_properties


def _assert_neo4j_legal(props: dict) -> None:
    """Neo4j: primitives or homogeneous arrays of primitives — never Map."""
    for key, value in props.items():
        assert value is not None, key
        if isinstance(value, dict):
            raise AssertionError(f"nested Map property {key!r}: {value!r}")
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    raise AssertionError(f"Map in array property {key!r}: {item!r}")
                assert isinstance(item, (str, int, float, bool)), (key, item)
            kinds = {type(x) for x in value}
            assert len(kinds) <= 1 or kinds <= {int, float}, (key, kinds)
        else:
            assert isinstance(value, (str, int, float, bool)), (key, type(value), value)


def test_neo4j_safe_properties_stringifies_interface_map() -> None:
    """The exact TypeError payload: Map{name, data_type, section}."""
    raw = {
        "pin": {"name": "timePt", "data_type": "Time", "section": "Input"},
        "call_params": [{"name": "timePt", "data_type": "Time", "section": "Input"}],
        "name": "OB1Main",
        "seq": 1,
        "flags": [True, False],
        "empty": None,
    }
    safe = neo4j_safe_properties(raw)
    _assert_neo4j_legal(safe)
    assert "empty" not in safe
    assert safe["name"] == "OB1Main"
    assert safe["seq"] == 1
    assert json.loads(safe["pin"]) == {"name": "timePt", "data_type": "Time", "section": "Input"}
    assert json.loads(safe["call_params"])[0]["name"] == "timePt"


def test_plc_kg_publish_flattens_call_param_maps() -> None:
    kg = PlcKnowledgeGraph()
    kg.add_node("Project::Demo", "Project", name="Demo")
    kg.add_node("Block::OB1Main", "Block", name="OB1Main", block_type="OB")
    kg.add_node("Block::FB1000", "Block", name="FB1000", block_type="FB")
    kg.add_node(
        "Variable::FB1000::Input::timePt",
        "Variable",
        name="timePt",
        data_type="Time",
        section="Input",
    )
    kg.add_edge("Project::Demo", "Block::OB1Main", "CONTAINS")
    kg.add_edge(
        "Block::OB1Main",
        "Block::FB1000",
        "CALLS",
        evidence="xml_call",
        seq=1,
        call_params=[{"name": "timePt", "data_type": "Time", "section": "Input"}],
    )
    kg.add_edge(
        "Block::FB1000",
        "Variable::FB1000::Input::timePt",
        "HAS_INTERFACE",
        section="Input",
    )
    # Nested map stuffed onto a node (would SET n += Map and raise TypeError)
    kg.add_node(
        "Block::FB1000",
        "Block",
        interface_pin={"name": "timePt", "data_type": "Time", "section": "Input"},
    )

    entities, relations = plc_kg_to_entities_relations(kg, project_key="Demo")
    for ent in entities:
        _assert_neo4j_legal(ent.properties)
    for rel in relations:
        _assert_neo4j_legal(rel.properties)

    calls = [r for r in relations if r.type == "CALLS"]
    assert len(calls) == 1
    params = json.loads(calls[0].properties["call_params"])
    assert params == [{"name": "timePt", "data_type": "Time", "section": "Input"}]
    assert calls[0].properties["evidence"] == "xml_call"

    iface = [r for r in relations if r.type == "HAS_INTERFACE"]
    assert len(iface) == 1
    assert iface[0].properties["section"] == "Input"

    var = next(e for e in entities if e.type == "PLCVariable")
    assert var.properties["name"] == "timePt"
    assert var.properties["data_type"] == "Time"
    assert var.properties["section"] == "Input"

    fb = next(e for e in entities if e.canonical_key.endswith("Block::FB1000"))
    assert json.loads(fb.properties["interface_pin"])["name"] == "timePt"


def test_publish_plc_knowledge_graph_memory_backend(monkeypatch) -> None:
    from knowledge.retrieval.graph import InMemoryKnowledgeGraph

    monkeypatch.setattr(
        "agents.plc.tia.neo4j_publish.create_knowledge_graph",
        lambda: InMemoryKnowledgeGraph(),
    )
    kg = PlcKnowledgeGraph()
    kg.add_node("Block::A", "Block", name="A")
    kg.add_node("Block::B", "Block", name="B")
    kg.add_edge(
        "Block::A",
        "Block::B",
        "CALLS",
        call_params=[{"name": "timePt", "data_type": "Time", "section": "Input"}],
    )
    out = publish_plc_knowledge_graph(kg, project_name="Demo")
    assert out["ok"] is True
    assert out["entities"] >= 2
    assert out["relations"] >= 1
