"""Best-effort hardware / Profinet parse from Openness HW XML.

Skip (do not fail the job) when no device/rack XML is present.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from agents.plc.tia.ir import HardwareDevice, PlcProject

_DEVICE_TAGS = {
    "Device",
    "DeviceItem",
    "HW.Devices.Device",
    "HW.Device",
    "SW.Devices.Device",
    "Rack",
    "Module",
}

_SKIP_NAMES = {"conversionlog", "gsdml"}


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _attr(el: ET.Element, name: str) -> str:
    return el.get(name) or ""


def _child_text(el: ET.Element, *names: str) -> str:
    want = {n.lower() for n in names}
    for child in el:
        if _strip_ns(child.tag).lower() in want and (child.text or "").strip():
            return (child.text or "").strip()
    for node in el.iter():
        if _strip_ns(node.tag).lower() in want and (node.text or "").strip():
            return (node.text or "").strip()
    return ""


def looks_like_hardware_xml(path: Path) -> bool:
    name = path.name.lower()
    if any(skip in name for skip in _SKIP_NAMES):
        return False
    parts = {p.lower() for p in path.parts}
    if "gsd" in parts:
        return False
    try:
        head = path.read_bytes()[:8192].decode("utf-8", errors="ignore")
    except OSError:
        return False
    markers = (
        "HW.Devices",
        "HW.Device",
        "DeviceItem",
        "ProfinetInterface",
        "Siemens.Engineering.HW",
        "<Rack",
        "CompositionName=\"Devices\"",
    )
    return any(m in head for m in markers)


def parse_hardware_xml(path: Path) -> list[HardwareDevice]:
    """Extract device/rack/Profinet rows; empty list on unrecognized XML."""
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except ET.ParseError:
        return []
    devices: list[HardwareDevice] = []
    seen: set[tuple[str, str]] = set()
    for node in root.iter():
        tag = _strip_ns(node.tag)
        if tag not in _DEVICE_TAGS and "Device" not in tag and tag not in {"ProfinetInterface"}:
            continue
        name = _attr(node, "Name") or _child_text(node, "Name", "DeviceName")
        if not name:
            continue
        dtype = (
            _attr(node, "TypeIdentifier")
            or _attr(node, "Type")
            or _child_text(node, "TypeIdentifier", "TypeName", "Type")
            or tag
        )
        address = (
            _attr(node, "Address")
            or _child_text(node, "Address", "IpAddress", "LogicalAddress")
        )
        slot = _attr(node, "Slot") or _child_text(node, "Slot", "PositionNumber")
        comment = _child_text(node, "Comment", "Text")
        key = (name, dtype)
        if key in seen:
            continue
        seen.add(key)
        devices.append(
            HardwareDevice(
                name=name,
                device_type=dtype,
                address=address,
                slot=slot,
                comment=comment[:240],
                source_file=str(path),
            )
        )
    return devices


def attach_hardware(project: PlcProject, xml_files: list[Path]) -> PlcProject:
    """Fill ``project.hardware`` from any HW XML; never raise into the job."""
    found: list[HardwareDevice] = []
    for path in xml_files:
        if not looks_like_hardware_xml(path):
            continue
        try:
            found.extend(parse_hardware_xml(path))
        except Exception as exc:  # noqa: BLE001 — hardware is advisory
            project.extraction_notes.append(f"hardware parse skipped for {path.name}: {exc}")
    project.hardware = found
    return project
