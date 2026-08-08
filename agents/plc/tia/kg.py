"""Knowledge Graph builder — PLC-IR -> typed graph for agent queries.

Node types: Project, Block, Variable, Network, TagTable, Tag
Edge types:
  CONTAINS, HAS_INTERFACE,
  CALLS       — OB/FC/FB calls another block (CallInfo)
  USES        — block uses a DB / instance DB (global DB root or Instance)
  INSTANCE_OF — instance DB typed from an FB
  READS / WRITES — signal-level access
  NEXT        — successive callees in one caller

Association model (engineer view):
  Main --CALLS--> ce (FC)
  Main --USES-->  ceD (GlobalDB parameter store)
  ce   --USES-->  IEC_Counter_0_DB (CTU instance)
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

MOVE_PARTS = {"Move", "Assign", "Move_Bool", "Move_Word", "Move_DWord", "Move_Real"}
CALL_PARTS = {"Call", "CallPart"}
INSTANCE_BOX_PARTS = {"CTU", "CTD", "CTUD", "TON", "TOF", "TP"}
#: Move / Call / timer-counter pins that write an IdentCon target
WRITE_PINS = {
    "out",
    "out1",
    "out2",
    "out3",
    "OUT",
    "OUT1",
    "CV",
    "Q",
    "QU",
    "QD",
    "ET",
}


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
    _edge_keys: set[tuple[str, str, str]] = field(default_factory=set, repr=False)

    def add_node(self, node_id: str, node_type: str, **props: Any) -> None:
        if node_id in self.nodes:
            self.nodes[node_id].props.update({k: v for k, v in props.items() if v is not None})
        else:
            self.nodes[node_id] = GraphNode(id=node_id, type=node_type, props=props)

    def add_edge(self, source: str, target: str, edge_type: str, **props: Any) -> None:
        key = (source, target, edge_type)
        if key in self._edge_keys:
            # Merge props onto existing edge of same triple
            for edge in self.edges:
                if edge.source == source and edge.target == target and edge.type == edge_type:
                    edge.props.update({k: v for k, v in props.items() if v})
                    return
            return
        self._edge_keys.add(key)
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

    def users_of(self, block_name: str) -> list[str]:
        return sorted(
            {
                e.source.split("::", 1)[1]
                for e in self.in_edges(f"Block::{block_name}", "USES")
                if "::" in e.source
            }
        )

    def uses_of(self, block_name: str) -> list[str]:
        return sorted(
            {
                e.target.split("::", 1)[1]
                for e in self.out_edges(f"Block::{block_name}", "USES")
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


def _access_ref(access: Access) -> str:
    """Canonical reference string for accesses."""
    if access.scope == AccessScope.LOCAL:
        return f"#{access.root}" + (("." + ".".join(access.path)) if access.path else "")
    if access.path:
        return f"{access.root}.{'.'.join(access.path)}"
    return access.root or access.raw or access.absolute


def _access_bound_to_pin(network: Network, part_uuid: str, pin: str) -> Access | None:
    """Resolve Access on a pin regardless of wire direction (in or out)."""
    for wire in network.wires:
        for endpoint in wire.endpoints:
            if endpoint.kind != "namecon" or endpoint.uuid != part_uuid or endpoint.pin != pin:
                continue
            for other in wire.endpoints:
                if other.kind == "identcon":
                    return network.access_parts.get(other.uuid)
    return None


def _pin_source_access(network: Network, part_uuid: str, pin: str) -> Access | None:
    """Resolve the Access feeding a part pin via IdentCon → NameCon wiring."""
    for wire in network.wires:
        for ep in wire.targets:
            if ep.kind == "namecon" and ep.uuid == part_uuid and ep.pin == pin:
                src = wire.source
                if src and src.kind == "identcon":
                    return network.access_parts.get(src.uuid)
    return None


def _network_block_refs(network: Network) -> list[tuple[str, dict[str, Any]]]:
    """Block calls from this network (FB/FC), with XML-derived evidence props.

    Prefer ``CallInfo`` / TemplateValue ``Call`` (the called block type/name).
    Never invent callees from network titles.
    """
    refs: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for part in network.parts.values():
        called = (
            part.template_values.get("Call")
            or part.template_values.get("calledBlock")
            or ""
        ).strip().strip('"')
        props: dict[str, Any] = {
            "part_uid": part.uuid,
            "block_type": part.template_values.get("BlockType") or "",
            "instance_db": part.template_values.get("InstanceDB") or "",
            "evidence": "xml_call",
        }
        if called:
            if called not in seen:
                seen.add(called)
                refs.append((called, props))
            continue
        if part.name in CALL_PARTS or (part.name or "").startswith("Call"):
            instance = (
                part.accesses.get("instance")
                or part.accesses.get("Instance")
                or _pin_source_access(network, part.uuid, "db")
                or _pin_source_access(network, part.uuid, "instance")
            )
            if instance and instance.root and instance.root not in seen:
                seen.add(instance.root)
                props["evidence"] = "xml_call_instance"
                props["instance_db"] = instance.root
                refs.append((instance.root, props))
    return refs


def _ensure_block_node(
    kg: PlcKnowledgeGraph,
    name: str,
    *,
    block_type: str | None = None,
    external: bool | None = None,
    **props: Any,
) -> str:
    block_id = f"Block::{name}"
    kg.add_node(
        block_id,
        "Block",
        name=name,
        block_type=block_type,
        external=external,
        **props,
    )
    return block_id


def _link_uses_db(
    kg: PlcKnowledgeGraph,
    block_id: str,
    db_name: str,
    *,
    known_blocks: dict[str, Block],
    evidence: str,
    network: str = "",
) -> None:
    if not db_name or f"Block::{db_name}" == block_id:
        return
    known = known_blocks.get(db_name)
    btype = known.block_type.value if known is not None else "DB"
    _ensure_block_node(
        kg,
        db_name,
        block_type=btype,
        external=known is None,
    )
    kg.add_edge(
        block_id,
        f"Block::{db_name}",
        "USES",
        evidence=evidence,
        **({"network": network} if network else {}),
    )


def _classify_part_io(
    block: Block,
    network: Network,
    kg: PlcKnowledgeGraph,
    *,
    known_blocks: dict[str, Block],
) -> None:
    block_id = f"Block::{block.name}"
    write_access_ids: set[str] = set()

    # Coil / Move / Call / box outputs → WRITES
    for part in network.parts.values():
        write_accesses: list[Access] = []
        if part.name in {"Coil", "NegCoil", "NotCoil", "Set", "Reset", "Save"}:
            operand = _pin_source_access(network, part.uuid, "operand") or part.accesses.get("operand")
            if operand is not None:
                write_accesses.append(operand)
        elif part.name in MOVE_PARTS or (part.name or "").startswith("Move"):
            for pin in ("out", "out1", "OUT", "OUT1"):
                acc = _access_bound_to_pin(network, part.uuid, pin)
                if acc is not None:
                    write_accesses.append(acc)
                    break
        elif part.name in CALL_PARTS or part.template_values.get("Call"):
            for wire in network.wires:
                for ep in wire.endpoints:
                    if ep.kind != "namecon" or ep.uuid != part.uuid:
                        continue
                    pin = ep.pin or ""
                    if not (pin.lower().startswith("out") or pin in WRITE_PINS):
                        continue
                    acc = _access_bound_to_pin(network, part.uuid, pin)
                    if acc is not None:
                        write_accesses.append(acc)
        elif part.name in INSTANCE_BOX_PARTS:
            for pin in ("CV", "Q", "QU", "QD", "ET"):
                acc = _access_bound_to_pin(network, part.uuid, pin)
                if acc is not None:
                    write_accesses.append(acc)

        for access in write_accesses:
            if not access.root and not access.absolute:
                continue
            ref = _access_ref(access)
            kg.add_node(f"Tag::{ref}", "Tag", name=ref, scope=access.scope.value)
            kg.add_edge(block_id, f"Tag::{ref}", "WRITES", part=part.name, network=network.id)
            for uid, acc in network.access_parts.items():
                if acc is access:
                    write_access_ids.add(uid)
            # Global DB root → USES Block::DB
            if access.scope == AccessScope.GLOBAL and access.root:
                root_block = known_blocks.get(access.root)
                if root_block is not None and root_block.block_type == BlockType.DB:
                    _link_uses_db(
                        kg,
                        block_id,
                        access.root,
                        known_blocks=known_blocks,
                        evidence="xml_db_write",
                        network=network.id,
                    )

    # Remaining network accesses are reads (+ USES for DB roots)
    for uid, access in network.access_parts.items():
        if uid in write_access_ids or access.scope == AccessScope.LITERAL:
            continue
        if not access.root and not access.absolute:
            continue
        ref = _access_ref(access)
        kg.add_node(f"Tag::{ref}", "Tag", name=ref, scope=access.scope.value)
        kg.add_edge(block_id, f"Tag::{ref}", "READS", network=network.id)
        if access.scope == AccessScope.GLOBAL and access.root:
            root_block = known_blocks.get(access.root)
            if root_block is not None and root_block.block_type == BlockType.DB:
                _link_uses_db(
                    kg,
                    block_id,
                    access.root,
                    known_blocks=known_blocks,
                    evidence="xml_db_read",
                    network=network.id,
                )

    # Timer / counter / FB instance DB → USES
    for part in network.parts.values():
        inst = part.accesses.get("instance") or part.accesses.get("Instance")
        inst_name = ""
        if inst is not None and inst.root:
            inst_name = inst.root
        elif part.template_values.get("InstanceDB"):
            inst_name = str(part.template_values["InstanceDB"]).strip().strip('"')
        if not inst_name:
            continue
        if part.name in INSTANCE_BOX_PARTS or part.template_values.get("Call"):
            _link_uses_db(
                kg,
                block_id,
                inst_name,
                known_blocks=known_blocks,
                evidence="xml_instance",
                network=network.id,
            )


def build_knowledge_graph(project: PlcProject) -> PlcKnowledgeGraph:
    kg = PlcKnowledgeGraph()
    project_id = f"Project::{project.name}"
    kg.add_node(project_id, "Project", name=project.name, tia_version=project.tia_version)
    known_blocks = dict(project.blocks)

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

    # Blocks (declare first so USES can resolve DB types)
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

    # Networks / calls / IO / USES
    for block in project.blocks.values():
        block_id = f"Block::{block.name}"
        for net_idx, network in enumerate(block.networks, start=1):
            net_id = f"Network::{block.name}::{network.id or len(kg.edges)}"
            kg.add_node(
                net_id,
                "Network",
                title=network.title,
                language=network.programming_language,
            )
            kg.add_edge(block_id, net_id, "CONTAINS")
            _classify_part_io(block, network, kg, known_blocks=known_blocks)

            for callee, call_props in _network_block_refs(network):
                if not callee or callee == block.name:
                    continue
                callee_known = known_blocks.get(callee)
                callee_type = (
                    call_props.get("block_type")
                    or (callee_known.block_type.value if callee_known else None)
                )
                _ensure_block_node(
                    kg,
                    callee,
                    block_type=callee_type,
                    external=callee not in project.blocks,
                )
                kg.add_edge(
                    block_id,
                    f"Block::{callee}",
                    "CALLS",
                    network=net_id,
                    seq=net_idx,
                    **{k: v for k, v in call_props.items() if v},
                )
                # FB instance DB: USES + INSTANCE_OF
                inst = str(call_props.get("instance_db") or "")
                if inst and inst != callee:
                    _link_uses_db(
                        kg,
                        block_id,
                        inst,
                        known_blocks=known_blocks,
                        evidence="xml_call_instance",
                        network=net_id,
                    )
                    if (call_props.get("block_type") or "") == "FB" or (
                        callee_known is not None and callee_known.block_type == BlockType.FB
                    ):
                        _ensure_block_node(kg, inst, block_type="DB", external=inst not in project.blocks)
                        kg.add_edge(f"Block::{inst}", f"Block::{callee}", "INSTANCE_OF")

        # Runtime sequence within this block: NEXT between successive unique callees
        ordered_callees: list[str] = []
        for network in block.networks:
            for callee, _props in _network_block_refs(network):
                if callee and callee != block.name and callee not in ordered_callees:
                    ordered_callees.append(callee)
        for i in range(len(ordered_callees) - 1):
            kg.add_edge(
                f"Block::{ordered_callees[i]}",
                f"Block::{ordered_callees[i + 1]}",
                "NEXT",
                seq=i + 1,
                evidence="xml_call_order",
            )

    # DB <-> FB instance dependencies from DB attributes
    fb_names = {b.name for b in project.blocks.values() if b.block_type == BlockType.FB}
    for block in project.blocks.values():
        if block.block_type != BlockType.DB:
            continue
        type_attr = block.attributes.get("OfType") or block.attributes.get("OfBlock") or ""
        if type_attr in fb_names:
            kg.add_edge(f"Block::{block.name}", f"Block::{type_attr}", "INSTANCE_OF")

    return kg
