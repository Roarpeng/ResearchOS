"""PLC-IR — language-agnostic intermediate representation for TIA projects.

Pipeline position: TIA Project -> Openness export (SimaticML XML) -> Extract
-> **PLC-IR** -> Knowledge Graph / SCL translation / LLM Agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class BlockType(StrEnum):
    FB = "FB"
    FC = "FC"
    OB = "OB"
    DB = "DB"
    UDT = "UDT"


class InterfaceSection(StrEnum):
    INPUT = "Input"
    OUTPUT = "Output"
    IN_OUT = "InOut"
    STATIC = "Static"
    TEMP = "Temp"
    CONSTANT = "Constant"
    RETURN = "Return"


class AccessScope(StrEnum):
    LOCAL = "local"      # #Variable
    GLOBAL = "global"    # "TagTable".Tag / direct address
    LITERAL = "literal"  # constant value
    UNKNOWN = "unknown"


@dataclass
class Access:
    """A variable/constant reference inside an instruction."""

    scope: AccessScope = AccessScope.UNKNOWN
    root: str = ""        # "#Var" -> Var ; global -> tag table name
    path: tuple[str, ...] = ()  # member chain after the root
    data_type: str = ""
    negated: bool = False
    raw: str = ""

    @property
    def name(self) -> str:
        base = self.root or self.raw
        if self.path:
            return ".".join([base, *self.path]) if self.scope != AccessScope.LOCAL else (
                base + "." + ".".join(self.path)
            )
        return base

    def as_scl(self) -> str:
        """Render the access as an SCL operand."""
        if self.scope == AccessScope.LITERAL:
            return self.raw
        if self.scope == AccessScope.LOCAL:
            core = "#" + self.root
        else:
            core = f'"{self.root}"' if self.root else self.raw
        if self.path:
            core = core + "." + ".".join(self.path)
        return f"NOT ({core})" if self.negated else core


@dataclass
class Variable:
    name: str
    section: InterfaceSection = InterfaceSection.STATIC
    data_type: str = ""
    start_value: str = ""
    comment: str = ""
    is_retain: bool = False
    logical_address: str = ""


@dataclass
class Part:
    """One instruction element in a network (contact, coil, call, timer...)."""

    name: str
    part_type: str
    uuid: str = ""
    version: str = ""
    accesses: dict[str, Access] = field(default_factory=dict)
    template_values: dict[str, str] = field(default_factory=dict)
    negated: bool = False
    programming_language: str = ""


@dataclass
class WireEndpoint:
    """One endpoint of a SimaticML wire.

    kind: powerrail | namecon | identcon | opencon
    - namecon: named pin of a Part (uuid + pin)
    - identcon: reference to a top-level Access part (uuid)
    """

    kind: str
    uuid: str = ""
    pin: str = ""


@dataclass
class Wire:
    """SimaticML wire: first endpoint is the source, rest are targets."""

    uid: str
    endpoints: list[WireEndpoint] = field(default_factory=list)

    @property
    def source(self) -> WireEndpoint | None:
        return self.endpoints[0] if self.endpoints else None

    @property
    def targets(self) -> list[WireEndpoint]:
        return self.endpoints[1:]


@dataclass
class Network:
    id: str = ""
    title: str = ""
    comment: str = ""
    programming_language: str = ""
    parts: dict[str, Part] = field(default_factory=dict)
    access_parts: dict[str, Access] = field(default_factory=dict)
    rails: dict[str, Part] = field(default_factory=dict)
    wires: list[Wire] = field(default_factory=list)
    source_text: str = ""  # SCL/STL body when the unit is textual

    def accesses(self) -> list[Access]:
        out: list[Access] = list(self.access_parts.values())
        for part in self.parts.values():
            out.extend(part.accesses.values())
        return out


@dataclass
class Block:
    name: str
    number: int = 0
    block_type: BlockType = BlockType.FB
    programming_language: str = ""
    namespace: str = ""
    header_comment: str = ""
    interface: list[Variable] = field(default_factory=list)
    networks: list[Network] = field(default_factory=list)
    source_text: str = ""  # original SCL/STL body when language is textual
    attributes: dict[str, str] = field(default_factory=dict)
    source_file: str = ""  # path to original SimaticML XML export

    def interface_section(self, section: InterfaceSection) -> list[Variable]:
        return [v for v in self.interface if v.section == section]

    def find_variable(self, name: str) -> Variable | None:
        for v in self.interface:
            if v.name == name:
                return v
        return None

    def is_protected(self) -> bool:
        """True when know-how / password protection should block SCL conversion."""
        truthy = {"true", "1", "yes", "on", "protected", "enabled"}
        for key, raw in self.attributes.items():
            k = key.lower().replace("-", "").replace("_", "")
            v = (raw or "").strip().lower()
            if "knowhow" in k or "protect" in k:
                if v in truthy or v == "":
                    return True
        blob = f"{self.header_comment} {self.source_text}".lower()
        return "know-how" in blob or "knowhow protect" in blob


@dataclass
class Tag:
    name: str
    data_type: str = ""
    logical_address: str = ""
    comment: str = ""


@dataclass
class TagTable:
    name: str
    tags: list[Tag] = field(default_factory=list)


@dataclass
class PlcProject:
    """Top-level PLC-IR container."""

    name: str = "TiaProject"
    tia_version: str = ""
    source_path: str = ""
    blocks: dict[str, Block] = field(default_factory=dict)
    tag_tables: dict[str, TagTable] = field(default_factory=dict)
    extraction_notes: list[str] = field(default_factory=list)

    def add_block(self, block: Block) -> None:
        self.blocks[block.name] = block

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for block in self.blocks.values():
            counts[block.block_type.value] = counts.get(block.block_type.value, 0) + 1
        counts["TagTables"] = len(self.tag_tables)
        counts["Networks"] = sum(len(b.networks) for b in self.blocks.values())
        return counts
