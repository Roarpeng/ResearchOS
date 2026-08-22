"""CAD asset MCP — metadata/structure-tree extraction per docs/industrial/03.

Text-level STEP (ISO-10303-21) parsing only: no geometry kernel, no license-
encumbered formats. Thumbnails stay disabled (async worker out of scope).
"""

from __future__ import annotations

import re
from typing import Any

from tools._mcp_compat import create_mcp_server

mcp = create_mcp_server("cad")

_LOCKED_TOOLS = {"thumbnail"}


@mcp.tool(name="cad.asset.register")
def cad_asset_register(
    name: str,
    fmt: str = "step",
    object_key: str | None = None,
    notes: str = "",
) -> dict[str, Any]:
    """Register a neutral-format research copy (never the PLM master)."""
    if not name.strip():
        return {"ok": False, "error": "invalid_argument", "detail": "name required"}
    return {
        "ok": True,
        "asset_id": f"cad_{abs(hash((name, object_key or ''))) % 10_000_000:08d}",
        "name": name,
        "format": fmt.lower(),
        "object_key": object_key,
        "notes": notes[:400],
        "readonly_copy": True,
    }


def extract_step_structure(text: str) -> dict[str, Any]:
    """Parse PRODUCT/PRODUCT_DEFINITION entities into a coarse structure tree."""
    products = re.findall(
        r"PRODUCT\s*\(\s*'([^']*)'\s*,\s*'([^']*)'", text, flags=re.IGNORECASE
    )
    assemblies = re.findall(r"NEXT_ASSEMBLY_USAGE_OCCURRENCE", text, flags=re.IGNORECASE)
    parts = [
        {"name": (name or "").strip(), "description": (desc or "").strip()}
        for name, desc in products
    ]
    seen: set[str] = set()
    uniq_parts = [p for p in parts if not (p["name"] in seen or seen.add(p["name"]))]
    return {
        "kind": "step",
        "part_count": len(uniq_parts),
        "assembly_usages": len(assemblies),
        "parts": uniq_parts[:256],
        "is_assembly": len(uniq_parts) > 1 or len(assemblies) > 0,
    }


@mcp.tool(name="cad.meta.extract")
def cad_meta_extract(step_text: str, name: str = "") -> dict[str, Any]:
    """Extract metadata + coarse structure tree from STEP source text."""
    if not (step_text or "").strip():
        return {"ok": False, "error": "invalid_argument", "detail": "step_text empty"}
    header = re.search(r"FILE_NAME\s*\(\s*'([^']*)'", step_text, flags=re.IGNORECASE)
    structure = extract_step_structure(step_text)
    return {
        "ok": True,
        "name": name or (header.group(1) if header else ""),
        **structure,
    }


@mcp.tool(name="cad.bom.suggest")
def cad_bom_suggest(structure_query: str, top_k: int = 6) -> dict[str, Any]:
    """Knowledge-backed BOM hints from the structure description (best effort)."""
    try:
        from knowledge.pipeline import KnowledgePipeline

        pack = KnowledgePipeline().search(structure_query, top_k=max(1, min(int(top_k), 20)))
        passages = [
            {
                "text": p.get("text", "")[:240],
                "citation": p.get("citation"),
                "source_id": p.get("source_id"),
            }
            for p in (pack.get("passages") or [])
        ]
    except Exception:  # noqa: BLE001 — knowledge layer optional here
        passages = []
    return {"ok": True, "suggestions": passages}


@mcp.tool(name="cad.diff.revisions")
def cad_diff_revisions(text_a: str, text_b: str) -> dict[str, Any]:
    """Part-name set diff between two STEP revisions (when parseable)."""
    try:
        a = {p["name"] for p in extract_step_structure(text_a)["parts"]}
        b = {p["name"] for p in extract_step_structure(text_b)["parts"]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "parse_failed", "detail": str(exc)[:200]}
    return {
        "ok": True,
        "added": sorted(b - a)[:128],
        "removed": sorted(a - b)[:128],
        "unchanged_count": len(a & b),
    }


@mcp.tool(name="cad.view.thumbnail")
def cad_view_thumbnail(asset_id: str) -> dict[str, Any]:
    """Async preview jobs are handled by an external worker; disabled here."""
    return {"ok": False, "error": "not_enabled", "detail": "thumbnail worker not configured"}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
