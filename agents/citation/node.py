"""Citation Agent node: evidence → citations with stable C# ids."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from runtime.researchos_runtime.state import TaskState


def run(state: TaskState) -> dict[str, Any]:
    evidence = list(state.get("evidence") or [])
    existing = list(state.get("citations") or [])
    seen_keys: set[str] = set()
    for cit in existing:
        key = cit.get("url") or cit.get("evidence_id") or cit.get("id")
        if key:
            seen_keys.add(str(key))

    start_idx = len(existing) + 1
    new_citations: list[dict[str, Any]] = []
    evid_to_cid: dict[str, str] = {}

    for offset, item in enumerate(evidence):
        eid = str(item.get("id") or f"ev_{offset}")
        key = str(item.get("url") or item.get("source_id") or eid)
        if key in seen_keys:
            # map to existing if same evidence id already cited
            for cit in existing:
                if cit.get("evidence_id") == eid or cit.get("url") == item.get("url"):
                    evid_to_cid[eid] = str(cit.get("id"))
                    break
            continue

        cid = f"C{start_idx + len(new_citations)}"
        quote = (item.get("content") or "")[:240]
        new_citations.append(
            {
                "id": cid,
                "evidence_id": eid,
                "source_id": item.get("source_id") or item.get("url") or eid,
                "locator": item.get("locator") or "",
                "quote": quote,
                "url": item.get("url") or "",
                "title": item.get("title") or eid,
            }
        )
        evid_to_cid[eid] = cid
        seen_keys.add(key)

    # Rewrite analysis citation_ids from TMP:ev_* → C#
    analysis = dict(state.get("analysis_results") or {})
    updated_analysis: dict[str, Any] = {}
    for specialty, block in analysis.items():
        block = dict(block or {})
        raw_ids = list(block.get("citation_ids") or [])
        mapped: list[str] = []
        for ref in raw_ids:
            if isinstance(ref, str) and ref.startswith("TMP:"):
                eid = ref[4:]
                if eid in evid_to_cid:
                    mapped.append(evid_to_cid[eid])
            elif isinstance(ref, str) and ref.startswith("C"):
                mapped.append(ref)
            elif isinstance(ref, str) and ref in evid_to_cid:
                mapped.append(evid_to_cid[ref])
        # If analysis had no ids, attach all new citations
        if not mapped and evid_to_cid:
            mapped = list(dict.fromkeys(evid_to_cid.values()))
        block["citation_ids"] = mapped
        updated_analysis[specialty] = block

    now = datetime.now(timezone.utc).isoformat()
    out: dict[str, Any] = {
        "citations": new_citations,
        "events": [
            {
                "type": "citation.normalized",
                "task_id": state.get("task_id", ""),
                "payload": {"added": len(new_citations), "mapping": evid_to_cid},
                "ts": now,
            }
        ],
        "route": "reviewer",
        "meta": {
            **(state.get("meta") or {}),
            "citation_style": "footnote",
            "citation_mapping": evid_to_cid,
        },
    }
    if updated_analysis:
        out["analysis_results"] = updated_analysis
    return out
