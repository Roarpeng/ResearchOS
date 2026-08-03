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
        q = query.lower()
        hits = [
            e
            for e in FAKE_CATALOG
            if q in e.title.lower()
            or q in e.summary.lower()
            or q in e.vendor.lower()
            or q in e.family.lower()
        ]
        return hits[:limit]

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
