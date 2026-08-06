"""Knowledge Graph builder — PLC-IR -> typed graph for agent queries.

Node types: Project, Block, Variable, Network, Part, TagTable, Tag
Edge types: CONTAINS, HAS_INTERFACE, CALLS, READS, WRITES, INSTANCE_OF,
            DEFINED_IN, DEPENDS_ON

In-memory + JSON serializable; can later be pushed into Neo4j via the
knowledge layer without changing the extraction contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.plc.tia.ir import Access, AccessScope, Block, BlockType, Network, PlcProject

#: Parts whose primary Access pin writes state (coils, assignments, resets)
WRITE_PARTS = {
    "Coil",
    "NegCoil",
    "NotCoil",
    "Move",
    "Assign",
    "Reset",
    "Set",
    "Save",
}

CALL_PARTS = {"Call", "CallPart"}


@dataclass
class GraphNode:
    id: str
    type: str
    props: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source: str
    target: str
    type: str
    props: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlcKnowledgeGraph:
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)

    def add_node(self, node_id: str, node_type: str, **props: Any) -> None:
        if node_id in self.nodes:
            self.nodes[node_id].props.update(props)
        else:
            self.nodes[node_id] = GraphNode(id=node_id, type=node_type, props=props)

    def add_edge(self, source: str, target: str, edge_type: str, **props: Any) -> None:
        self.edges.append(GraphEdge(source=source, target=target, type=edge_type, props=props))

    # -- queries -----------------------------------------------------------
    def blocks(self) -> list[GraphNode]:
        return [n for n in self.nodes.values() if n.type == "Block"]

    def out_edges(self, node_id: str, edge_type: str | None = None) -> list[GraphEdge]:
        return [
            e for e in self.edges if e.source == node_id and (edge_type is None or e.type == edge_type)
        ]

    def in_edges(self, node_id: str, edge_type: str | None = None) -> list[GraphEdge]:
        return [
            e for e in self.edges if e.target == node_id and (edge_type is None or e.type == edge_type)
        ]

    def callers_of(self, block_name: str) -> list[str]:
        return sorted(
            {
                e.source.split("::", 1)[1]
                for e in self.in_edges(f"Block::{block_name}", "CALLS")
                if "::" in e.source
            }
        )

    def callees_of(self, block_name: str) -> list[str]:
        return sorted(
            {
                e.target.split("::", 1)[1]
                for e in self.out_edges(f"Block::{block_name}", "CALLS")
                if "::" in e.target
            }
        )

    def readers_of_tag(self, tag_ref: str) -> list[str]:
        return sorted(
            {
                e.source.split("::", 1)[1]
                for e in self.in_edges(f"Tag::{tag_ref}", "READS")
                if "::" in e.source
            }
        )

    def writers_of_tag(self, tag_ref: str) -> list[str]:
        return sorted(
            {
                e.source.split("::", 1)[1]
                for e in self.in_edges(f"Tag::{tag_ref}", "WRITES")
                if "::" in e.source
            }
        )
    def to_json(self) -> dict[str, Any]:
        return {
            "nodes": [
                {"id": n.id, "type": n.type, "props": n.props} for n in self.nodes.values()
            ],
            "edges": [
                {"source": e.source, "target": e.target, "type": e.type, "props": e.props}
                for e in self.edges
            ],
        }


def _access_ref(access) -> str:
    """Canonical reference string for global accesses."""
    if access.scope == AccessScope.LOCAL:
        return f"#{access.root}" + (("." + ".".join(access.path)) if access.path else "")
    if access.path:
        return f"{access.root}.{'.'.join(access.path)}"
    return access.root or access.raw


def _pin_source_access(network: Network, part_uuid: str, pin: str) -> Access | None:
    """Resolve the Access feeding a part pin via IdentCon wiring."""
    for wire in network.wires:
        for ep in wire.targets:
            if ep.kind == "namecon" and ep.uuid == part_uuid and ep.pin == pin:
                src = wire.source
                if src and src.kind == "identcon":
                    return network.access_parts.get(src.uuid)
    return None


def _network_block_refs(network: Network) -> set[str]:
    """Block names called from this network (FB calls / FC calls)."""
    refs: set[str] = set()
    for part in network.parts.values():
        called = part.template_values.get("Call") or part.template_values.get("calledBlock")
        if called:
            refs.add(called.strip().strip('"'))
            continue
        if part.name in CALL_PARTS or part.name.startswith("Call"):
            instance = (
                part.accesses.get("instance")
                or part.accesses.get("Instance")
                or _pin_source_access(network, part.uuid, "db")
                or _pin_source_access(network, part.uuid, "instance")
            )
            if instance and instance.root:
                refs.add(instance.root)
    return refs


def _classify_part_io(block: Block, network: Network, kg: PlcKnowledgeGraph) -> None:
    block_id = f"Block::{block.name}"
    write_access_ids: set[str] = set()

    # Coil-like parts write their operand pin
    for part in network.parts.values():
        if part.name in WRITE_PARTS or part.part_type in WRITE_PARTS:
            operand = _pin_source_access(network, part.uuid, "operand")
            if operand is None:
                operand = part.accesses.get("operand")
            if operand and operand.root:
                ref = _access_ref(operand)
                kg.add_node(f"Tag::{ref}", "Tag", name=ref, scope=operand.scope.value)
                kg.add_edge(block_id, f"Tag::{ref}", "WRITES", part=part.name, network=network.id)
                for uid, acc in network.access_parts.items():
                    if acc is operand:
                        write_access_ids.add(uid)

    # Remaining network accesses are reads
    for uid, access in network.access_parts.items():
        if uid in write_access_ids or access.scope == AccessScope.LITERAL or not access.root:
            continue
        ref = _access_ref(access)
        kg.add_node(f"Tag::{ref}", "Tag", name=ref, scope=access.scope.value)
        kg.add_edge(block_id, f"Tag::{ref}", "READS", network=network.id)


def build_knowledge_graph(project: PlcProject) -> PlcKnowledgeGraph:
    kg = PlcKnowledgeGraph()
    project_id = f"Project::{project.name}"
    kg.add_node(project_id, "Project", name=project.name, tia_version=project.tia_version)

    # Tag tables
    for table in project.tag_tables.values():
        table_id = f"TagTable::{table.name}"
        kg.add_node(table_id, "TagTable", name=table.name)
        kg.add_edge(project_id, table_id, "CONTAINS")
        for tag in table.tags:
            tag_id = f"Tag::{tag.name}"
            kg.add_node(
                tag_id,
                "Tag",
                name=tag.name,
                data_type=tag.data_type,
                address=tag.logical_address,
                comment=tag.comment,
            )
            kg.add_edge(table_id, tag_id, "CONTAINS")

    # Blocks
    for block in project.blocks.values():
        block_id = f"Block::{block.name}"
        kg.add_node(
            block_id,
            "Block",
            name=block.name,
            number=block.number,
            block_type=block.block_type.value,
            language=block.programming_language,
            comment=block.header_comment,
        )
        kg.add_edge(project_id, block_id, "CONTAINS")

        for var in block.interface:
            var_id = f"Variable::{block.name}::{var.name}"
            kg.add_node(
                var_id,
                "Variable",
                name=var.name,
                section=var.section.value,
                data_type=var.data_type,
                comment=var.comment,
            )
            kg.add_edge(block_id, var_id, "HAS_INTERFACE", section=var.section.value)

        for network in block.networks:
            net_id = f"Network::{block.name}::{network.id or len(kg.edges)}"
            kg.add_node(
                net_id,
                "Network",
                title=network.title,
                language=network.programming_language,
            )
            kg.add_edge(block_id, net_id, "CONTAINS")
            _classify_part_io(block, network, kg)

            for callee in _network_block_refs(network):
                callee = callee.strip().strip('"')
                if callee and callee != block.name:
                    kg.add_edge(block_id, f"Block::{callee}", "CALLS", network=net_id)
                    kg.add_node(f"Block::{callee}", "Block", name=callee, external=True)

    # DB <-> FB instance dependencies
    fb_names = {b.name for b in project.blocks.values() if b.block_type == BlockType.FB}
    for block in project.blocks.values():
        if block.block_type != BlockType.DB:
            continue
        type_attr = block.attributes.get("OfType") or block.attributes.get("OfBlock") or ""
        if type_attr in fb_names:
            kg.add_edge(f"Block::{block.name}", f"Block::{type_attr}", "INSTANCE_OF")

    return kg
