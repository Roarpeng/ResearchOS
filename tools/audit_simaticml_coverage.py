"""Audit all available TIA Openness exports for SimaticML parser coverage gaps."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from agents.plc.tia.flgnet_fold import fold_network
from agents.plc.tia.simaticml import parse_block_xml


def strip(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def attr_name(el: ET.Element, key: str) -> str:
    for ak, av in el.attrib.items():
        if ak == key or ak.endswith("}" + key) or ak.endswith(key):
            return av
    return ""


def main() -> None:
    roots: list[Path] = []
    tmp = Path(r"C:\Users\vboxuser\AppData\Local\Temp")
    for d in sorted(tmp.glob("researchos_tia_export_*"), key=lambda p: p.stat().st_mtime, reverse=True)[
        :15
    ]:
        roots.append(d)
    fixtures = Path("tests/fixtures")
    if fixtures.is_dir():
        roots.extend(sorted(fixtures.glob("tia_*")))

    xml_files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        xml_files.extend(root.rglob("*.xml"))
    print(f"roots={len(roots)} xml_files={len(xml_files)}")

    ns_children: Counter[str] = Counter()
    part_names: Counter[str] = Counter()
    call_instr: Counter[str] = Counter()
    stl_tokens: Counter[str] = Counter()
    langs: Counter[str] = Counter()
    block_roots: Counter[str] = Counter()
    access_scopes: Counter[str] = Counter()

    for xml in xml_files:
        try:
            root = ET.parse(xml).getroot()
        except ET.ParseError:
            continue
        for node in root.iter():
            t = strip(node.tag)
            if t.startswith("SW.Blocks.") or t.startswith("SW.Tags.") or t.startswith("SW.Types."):
                block_roots[t] += 1
            if t == "ProgrammingLanguage" and (node.text or "").strip():
                langs[(node.text or "").strip()] += 1
            if t == "NetworkSource":
                kids = [strip(c.tag) for c in list(node)]
                if not kids:
                    ns_children["(empty)"] += 1
                for k in kids:
                    ns_children[k] += 1
            if t == "Part":
                name = attr_name(node, "Name")
                if name:
                    part_names[name] += 1
            if t == "Instruction":
                name = attr_name(node, "Name")
                if name:
                    call_instr[name] += 1
            if t == "CallInfo":
                name = attr_name(node, "Name")
                if name:
                    call_instr[f"CallInfo:{name}"] += 1
            if t == "StlToken":
                text = attr_name(node, "Text")
                if text:
                    stl_tokens[text] += 1
            if t == "Access":
                scope = attr_name(node, "Scope")
                if scope:
                    access_scopes[scope] += 1

    print("\n=== NetworkSource children ===")
    for k, v in ns_children.most_common():
        print(f"  {k}: {v}")
    print("\n=== Part names ===")
    for k, v in part_names.most_common(60):
        print(f"  {k}: {v}")
    print("\n=== Instructions / CallInfo ===")
    for k, v in call_instr.most_common(60):
        print(f"  {k}: {v}")
    print("\n=== STL tokens ===")
    for k, v in stl_tokens.most_common(40):
        print(f"  {k}: {v}")
    print("\n=== Access scopes ===")
    for k, v in access_scopes.most_common():
        print(f"  {k}: {v}")
    print("\n=== ProgrammingLanguage ===")
    for k, v in langs.most_common():
        print(f"  {k}: {v}")
    print("\n=== Block roots ===")
    for k, v in block_roots.most_common(30):
        print(f"  {k}: {v}")

    # Newest file per basename
    by_name: dict[str, Path] = {}
    for xml in sorted(xml_files, key=lambda p: p.stat().st_mtime):
        by_name[xml.name] = xml

    print("\n=== Parse gaps (newest per filename) ===")
    gap = 0
    for name, xml in sorted(by_name.items()):
        try:
            block = parse_block_xml(xml)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {name}: {exc}")
            gap += 1
            continue
        if block is None:
            continue
        try:
            root = ET.parse(xml).getroot()
        except ET.ParseError:
            continue
        units = [u for u in root.iter() if strip(u.tag) == "SW.Blocks.CompileUnit"]
        for i, net in enumerate(block.networks, 1):
            if i - 1 >= len(units):
                break
            unit = units[i - 1]
            kids: list[str] = []
            for x in unit.iter():
                if strip(x.tag) == "NetworkSource":
                    kids = [strip(c.tag) for c in list(x)]
            ns_nonempty = bool(kids)
            empty_ir = not net.parts and not net.source_text and not net.wires
            if ns_nonempty and empty_ir:
                print(
                    f"  GAP {name} net{i}: XML={kids} IR empty lang={net.programming_language!r}"
                )
                gap += 1
                continue
            folded = fold_network(net)
            if net.parts and not folded.statements and not net.source_text:
                unresolved = folded.unresolved_parts
                if unresolved:
                    names = [p.name for p in net.parts.values()]
                    print(
                        f"  UNRESOLVED {name} net{i}: parts={names} unresolved={unresolved[:10]}"
                    )
                    gap += 1
    print(f"gap_signals={gap}")
    raise SystemExit(1 if gap else 0)


if __name__ == "__main__":
    main()
