"""SimaticML XML parser — Openness block/tag-table exports -> PLC-IR.

Every TIA block (LAD, FBD, SCL, STL, GRAPH) exports to SimaticML via
Openness `PlcBlock.Export(...)`. This module parses those exports into
the PLC-IR model without needing TIA Portal installed.

Supported document types:
- Simatic.ML          (FB / FC / OB blocks)
- Simatic.TagTable.ML (PLC tag tables)
- Simatic.TypeTable.ML / UDT exports (best-effort as DB/UDT interface)
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from agents.plc.tia.ir import (
    Access,
    AccessScope,
    Block,
    BlockType,
    InterfaceSection,
    Network,
    Part,
    PlcProject,
    Tag,
    TagTable,
    Variable,
    Wire,
    WireEndpoint,
)

_SECTION_MAP = {
    "Input": InterfaceSection.INPUT,
    "Output": InterfaceSection.OUTPUT,
    "InOut": InterfaceSection.IN_OUT,
    "Static": InterfaceSection.STATIC,
    "Temp": InterfaceSection.TEMP,
    "Constant": InterfaceSection.CONSTANT,
    "Return": InterfaceSection.RETURN,
}

_BLOCK_TYPE_BY_SUFFIX = {"FB": BlockType.FB, "FC": BlockType.FC, "OB": BlockType.OB, "DB": BlockType.DB}


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _children(el: ET.Element) -> list[ET.Element]:
    return list(el)


def _attr(el: ET.Element, name: str) -> str:
    return el.get(name) or ""


def _detect_document_type(root: ET.Element) -> str:
    for el in root.iter():
        if _strip_ns(el.tag) == "DocumentType":
            return (el.text or "").strip()
    return ""


# ---------------------------------------------------------------------------
# Access parsing
# ---------------------------------------------------------------------------

def parse_access(access_el: ET.Element) -> Access:
    scope_attr = _attr(access_el, "Scope")
    if scope_attr == "LocalVariable":
        scope = AccessScope.LOCAL
    elif scope_attr in {"GlobalVariable", "TypedValue"}:
        scope = AccessScope.GLOBAL
    elif scope_attr in {"Constant", "LiteralConstant"}:
        scope = AccessScope.LITERAL
    else:
        scope = AccessScope.UNKNOWN

    symbols: list[str] = []
    for node in access_el.iter():
        if _strip_ns(node.tag) == "Symbol":
            for comp in node:
                if _strip_ns(comp.tag) == "Component":
                    symbols.append(_attr(comp, "Name"))
    raw = ".".join(symbols)

    root = symbols[0] if symbols else ""
    if scope == AccessScope.LOCAL and root.startswith("#"):
        root = root[1:]
    path = tuple(symbols[1:]) if len(symbols) > 1 else ()

    data_type = ""
    for node in access_el.iter():
        if _strip_ns(node.tag) == "PredefinedAttribute":
            if _attr(node, "Name") == "DataType":
                data_type = _attr(node, "Value")
    return Access(
        scope=scope,
        root=root,
        path=path,
        data_type=data_type,
        raw=raw or _attr(access_el, "Name"),
    )


# ---------------------------------------------------------------------------
# Interface parsing
# ---------------------------------------------------------------------------

def _parse_member(member_el: ET.Element, section: InterfaceSection) -> Variable:
    name = _attr(member_el, "Name")
    data_type = _attr(member_el, "Datatype")
    start_value = ""
    comment = ""
    is_retain = False
    for node in member_el.iter():
        tag = _strip_ns(node.tag)
        if tag == "StartValue":
            start_value = (node.text or "").strip()
        elif tag == "Comment":
            for text_el in node.iter():
                if _strip_ns(text_el.tag) == "Text":
                    comment = (text_el.text or "").strip()
                    break
        elif tag == "Attribute":
            if _attr(node, "Name") == "SetpointAddress" and _attr(node, "Value") == "true":
                is_retain = True
    return Variable(
        name=name,
        section=section,
        data_type=data_type,
        start_value=start_value,
        comment=comment,
        is_retain=is_retain,
    )


def parse_interface(interface_el: ET.Element) -> list[Variable]:
    variables: list[Variable] = []
    for node in interface_el.iter():
        if _strip_ns(node.tag) != "Section":
            continue
        section = _SECTION_MAP.get(_attr(node, "Name"), InterfaceSection.STATIC)
        for member in node:
            if _strip_ns(member.tag) == "Member":
                variables.append(_parse_member(member, section))
    return variables


# ---------------------------------------------------------------------------
# Network / body parsing (LAD, FBD, SCL/STL passthrough)
# ---------------------------------------------------------------------------

def _parse_part(part_el: ET.Element) -> Part:
    part = Part(
        name=_attr(part_el, "Name"),
        part_type=_attr(part_el, "Name"),
        uuid=_attr(part_el, "UId"),
        version=_attr(part_el, "Version"),
    )
    for node in part_el:
        tag = _strip_ns(node.tag)
        if tag == "TemplateValue":
            part.template_values[_attr(node, "Name")] = (node.text or "").strip()
        elif tag == "Attribute" and _attr(node, "Name") == "Negated":
            part.negated = (node.text or "").strip().lower() == "true"
        elif tag == "Access":
            # Nested access (some call parts embed their instance access)
            access_name = _attr(node, "Name") or f"acc{len(part.accesses)}"
            part.accesses[access_name] = parse_access(node)
    return part


def _parse_wire(wire_el: ET.Element) -> Wire:
    endpoints: list[WireEndpoint] = []
    for node in wire_el:
        tag = _strip_ns(node.tag)
        if tag == "Powerrail":
            endpoints.append(WireEndpoint(kind="powerrail"))
        elif tag == "NameCon":
            endpoints.append(WireEndpoint(kind="namecon", uuid=_attr(node, "UId"), pin=_attr(node, "Name")))
        elif tag == "IdentCon":
            endpoints.append(WireEndpoint(kind="identcon", uuid=_attr(node, "UId")))
        elif tag == "OpenCon":
            endpoints.append(WireEndpoint(kind="opencon", uuid=_attr(node, "UId"), pin=_attr(node, "Name")))
    return Wire(uid=_attr(wire_el, "UId"), endpoints=endpoints)


def _ml_text(parent: ET.Element) -> str:
    """First <Text> content inside a MultilingualText(Item) subtree."""
    for text_el in parent.iter():
        if _strip_ns(text_el.tag) == "Text":
            return (text_el.text or "").strip()
    return ""


def parse_network(compile_unit: ET.Element) -> Network:
    network = Network(id=_attr(compile_unit, "UId"))
    # Title/Comment are MultilingualText compositions, not element tags
    for node in compile_unit.iter():
        if _strip_ns(node.tag) != "MultilingualText":
            continue
        comp = _attr(node, "CompositionName")
        if comp == "Title":
            network.title = _ml_text(node)
        elif comp == "Comment":
            text = _ml_text(node)
            if text:
                network.comment = (network.comment + " " + text).strip()
    # programming language: first ProgrammingLanguage inside the unit body
    for node in compile_unit.iter():
        if _strip_ns(node.tag) == "ProgrammingLanguage":
            network.programming_language = (node.text or "").strip()
            break

    body = None
    for node in compile_unit.iter():
        if _strip_ns(node.tag) == "FlgNet":
            body = node
            break
    if body is not None:
        for node in body:
            tag = _strip_ns(node.tag)
            if tag == "StructuredText":
                network.source_text = (node.text or "").strip()
            elif tag == "Parts":
                for part_el in node:
                    part_tag = _strip_ns(part_el.tag)
                    if part_tag == "Part":
                        part = _parse_part(part_el)
                        if part.name in {"LeftRail", "RightRail"}:
                            network.rails[part.name] = part
                        else:
                            network.parts[part.uuid or part.name] = part
                    elif part_tag == "Access":
                        uid = _attr(part_el, "UId")
                        network.access_parts[uid] = parse_access(part_el)
            elif tag == "Wires":
                for wire_el in node:
                    if _strip_ns(wire_el.tag) == "Wire":
                        network.wires.append(_parse_wire(wire_el))
    return network


def _extract_source_text(sw_object: ET.Element) -> str:
    """Best-effort extraction of textual bodies (SCL/STL stored in export)."""
    for node in sw_object.iter():
        if _strip_ns(node.tag) in {"SourceText", "Text"}:
            text = (node.text or "").strip()
            if text and len(text.splitlines()) > 1:
                return text
    return ""


# ---------------------------------------------------------------------------
# Block parsing
# ---------------------------------------------------------------------------

def parse_block_xml(path: Path) -> Block | None:
    tree = ET.parse(path)
    root = tree.getroot()
    doc_type = _detect_document_type(root)
    if not doc_type.startswith("Simatic"):
        return None

    # Locate SW.Blocks.ObjectSW / SW.Blocks.GlobalDB
    sw_obj = None
    for node in root.iter():
        if _strip_ns(node.tag) in {"SW.Blocks.ObjectSW", "SW.Blocks.GlobalDB", "SW.Types.PlcStruct"}:
            sw_obj = node
            break
    if sw_obj is None:
        return None

    name = _attr(sw_obj, "Name") or path.stem
    attrs: dict[str, str] = {}
    for node in sw_obj.iter():
        if _strip_ns(node.tag) == "AttributeList":
            for attr_el in node:
                tag = _strip_ns(attr_el.tag)
                if tag == "Attribute":
                    attrs[_attr(attr_el, "Name")] = (attr_el.text or "").strip()
                elif (attr_el.text or "").strip():
                    # SimaticML stores Name/Number as direct child elements
                    attrs.setdefault(tag, (attr_el.text or "").strip())
            break
    name = _attr(sw_obj, "Name") or attrs.get("Name") or path.stem

    block_type = BlockType.DB
    number = 0
    try:
        number = int(attrs.get("Number") or "0")
    except ValueError:
        number = 0
    is_udt = any(
        _strip_ns(node.tag) == "SW.Types.PlcStruct" for node in root.iter()
    )
    for node in sw_obj.iter():
        if _strip_ns(node.tag) == "Number":
            try:
                number = int((node.text or "0").strip())
            except ValueError:
                number = 0
    suffix = doc_type.split(".")[-1].upper()
    if suffix in _BLOCK_TYPE_BY_SUFFIX:
        block_type = _BLOCK_TYPE_BY_SUFFIX[suffix]
    elif is_udt or doc_type.endswith("TypeTable.ML"):
        block_type = BlockType.UDT

    lang = attrs.get("ProgrammingLanguage") or ""
    if not lang:
        for node in sw_obj.iter():
            if _strip_ns(node.tag) == "ProgrammingLanguage":
                lang = (node.text or "").strip()
                break

    interface: list[Variable] = []
    for node in sw_obj.iter():
        if (
            _strip_ns(node.tag) == "SW.Blocks.InterfaceSection"
            or _attr(node, "CompositionName") == "Interface"
        ):
            interface = parse_interface(node)
            break

    networks: list[Network] = []
    for node in sw_obj.iter():
        if _strip_ns(node.tag) == "SW.Blocks.CompileUnit":
            networks.append(parse_network(node))

    header_comment = ""
    for node in sw_obj.iter():
        if (
            _strip_ns(node.tag) == "MultilingualText"
            and _attr(node, "CompositionName") == "Comment"
        ):
            for text_el in node.iter():
                if _strip_ns(text_el.tag) == "Text":
                    header_comment = (text_el.text or "").strip()
                    break
            if header_comment:
                break

    return Block(
        name=name,
        number=number,
        block_type=block_type,
        programming_language=lang,
        header_comment=header_comment,
        interface=interface,
        networks=networks,
        source_text=_extract_source_text(sw_obj),
        attributes=attrs,
    )


def parse_tag_table_xml(path: Path) -> TagTable | None:
    tree = ET.parse(path)
    root = tree.getroot()
    doc_type = _detect_document_type(root)
    if "TagTable" not in doc_type and "Tag" not in doc_type:
        return None

    table_name = path.stem
    tags: list[Tag] = []
    for node in root.iter():
        if _strip_ns(node.tag) != "SW.Tags.PlcTag":
            continue
        name = _attr(node, "Name")
        data_type = ""
        address = ""
        comment = ""
        for sub in node.iter():
            sub_tag = _strip_ns(sub.tag)
            if sub_tag == "DataTypeName":
                data_type = (sub.text or "").strip()
            elif sub_tag == "LogicalAddress":
                address = (sub.text or "").strip()
            elif sub_tag == "MultilingualText" and _attr(sub, "CompositionName") == "Comment":
                comment = comment or _ml_text(sub)
            elif sub_tag == "Text" and not comment:
                comment = (sub.text or "").strip()
            elif sub_tag == "Name" and not name:
                # SimaticML keeps the tag name inside <AttributeList>
                name = (sub.text or "").strip()
        if name:
            tags.append(Tag(name=name, data_type=data_type, logical_address=address, comment=comment))
    if not tags:
        return None
    for node in root.iter():
        if _strip_ns(node.tag) != "SW.Tags.PlcTagTable":
            continue
        n = _attr(node, "Name")
        if not n:
            for sub in node.iter():
                if _strip_ns(sub.tag) == "Name":
                    n = (sub.text or "").strip()
                    break
        if n:
            table_name = n
        break
    return TagTable(name=table_name, tags=tags)


# ---------------------------------------------------------------------------
# Project extraction
# ---------------------------------------------------------------------------

def extract_project(export_dir: str | Path, *, project_name: str = "") -> PlcProject:
    """Scan an Openness export directory and build PLC-IR.

    Expected layout (flexible): any number of *.xml files exported via
    `PlcBlock.Export(..., ExportOptions.WithDefaults)` and tag tables.
    """
    export_path = Path(export_dir)
    project = PlcProject(name=project_name or export_path.name, source_path=str(export_path))
    if not export_path.exists():
        project.extraction_notes.append(f"export directory not found: {export_path}")
        return project

    xml_files = sorted(export_path.rglob("*.xml"))
    if not xml_files:
        project.extraction_notes.append("no XML exports found")
        return project

    skipped: list[str] = []
    for xml_file in xml_files:
        rel = str(xml_file.relative_to(export_path))
        try:
            block = parse_block_xml(xml_file)
            if block is not None:
                project.add_block(block)
                continue
        except ET.ParseError as exc:
            project.extraction_notes.append(f"parse error in {rel}: {exc}")
            continue
        except Exception as exc:  # noqa: BLE001 — keep pipeline advisory
            project.extraction_notes.append(f"block parse failed in {rel}: {exc}")
            continue
        try:
            table = parse_tag_table_xml(xml_file)
            if table is not None:
                project.tag_tables[table.name] = table
                continue
        except ET.ParseError as exc:
            project.extraction_notes.append(f"tag table parse error in {rel}: {exc}")
            continue
        except Exception as exc:  # noqa: BLE001
            project.extraction_notes.append(f"tag table parse failed in {rel}: {exc}")
            continue
        skipped.append(rel)

    if skipped:
        preview = ", ".join(skipped[:8])
        more = f" (+{len(skipped) - 8} more)" if len(skipped) > 8 else ""
        project.extraction_notes.append(
            f"unrecognized XML skipped ({len(skipped)}): {preview}{more}"
        )
    if not project.blocks and not project.tag_tables:
        project.extraction_notes.append(
            "no PLC blocks or tag tables recognized — check Openness export layout"
        )

    return project
