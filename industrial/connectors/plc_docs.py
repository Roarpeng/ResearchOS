"""PLC documentation connector — read-only stub with fake catalog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class PlcDocEntry:
    id: str
    title: str
    vendor: str
    family: str
    url: str
    summary: str
    tags: tuple[str, ...] = ()


class PlcDocsConnector(Protocol):
    def list_vendors(self) -> list[str]: ...

    def search(self, query: str, *, limit: int = 10) -> list[PlcDocEntry]: ...

    def get(self, doc_id: str) -> PlcDocEntry | None: ...


FAKE_CATALOG: list[PlcDocEntry] = [
    PlcDocEntry(
        id="plc_siemens_s7",
        title="SIMATIC S7-1500 System Manual",
        vendor="Siemens",
        family="S7-1500",
        url="https://example.com/plc/siemens-s7-1500",
        summary="CPU, I/O, and PROFINET commissioning overview for S7-1500.",
        tags=("plc", "profinet", "siemens"),
    ),
    PlcDocEntry(
        id="plc_beck_compactlogix",
        title="CompactLogix Controllers User Manual",
        vendor="Rockwell",
        family="CompactLogix",
        url="https://example.com/plc/compactlogix",
        summary="Controller architecture, EtherNet/IP, and ladder/ST guidance.",
        tags=("plc", "ethernet-ip", "rockwell"),
    ),
    PlcDocEntry(
        id="plc_beck_safety",
        title="Safety PLC Design Notes (stub)",
        vendor="Generic",
        family="Safety",
        url="https://example.com/plc/safety-notes",
        summary="Read-only safety design checklist; no download/write to field devices.",
        tags=("safety", "checklist"),
    ),
]


class FakePlcDocsConnector:
    def list_vendors(self) -> list[str]:
        return sorted({e.vendor for e in FAKE_CATALOG})

    def search(self, query: str, *, limit: int = 10) -> list[PlcDocEntry]:
        q = (query or "").strip().lower()
        if not q:
            return []

        def _haystack(e: PlcDocEntry) -> str:
            return " ".join(
                [e.title, e.summary, e.vendor, e.family, *e.tags]
            ).lower()

        # Exact phrase match first, then token-level scoring for compound queries.
        phrase_hits = [e for e in FAKE_CATALOG if q in _haystack(e)]
        if phrase_hits:
            return phrase_hits[:limit]

        tokens = [t for t in q.replace("-", " ").split() if len(t) >= 3]
        scored: list[tuple[int, int, PlcDocEntry]] = []
        for order, e in enumerate(FAKE_CATALOG):
            hay = _haystack(e)
            score = sum(1 for t in tokens if t in hay)
            if score:
                scored.append((score, order, e))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [e for _, _, e in scored[:limit]]

    def get(self, doc_id: str) -> PlcDocEntry | None:
        for e in FAKE_CATALOG:
            if e.id == doc_id:
                return e
        return None

    def as_dict(self, entry: PlcDocEntry) -> dict[str, Any]:
        return {
            "id": entry.id,
            "title": entry.title,
            "vendor": entry.vendor,
            "family": entry.family,
            "url": entry.url,
            "summary": entry.summary,
            "tags": list(entry.tags),
            "readonly": True,
        }
