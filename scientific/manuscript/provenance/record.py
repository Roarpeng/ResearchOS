"""Provenance: claim ↔ chunk ↔ source records (mirrors scientific/schemas/provenance.json)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SourceRef:
    source_id: str
    chunk_ids: list[str] = field(default_factory=list)
    locator: str | None = None
    quote: str | None = None
    doi: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProvenanceRecord:
    claim_id: str
    claim_text: str
    created_at: str
    task_id: str | None = None
    stage: str | None = None
    sources: list[SourceRef] = field(default_factory=list)
    confidence: str = "medium"
    verified: bool = False
    artifact_id: str | None = None
    model: str | None = None
    prompt_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["sources"] = [s.to_dict() for s in self.sources]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ProvenanceRecord":
        sources = [SourceRef(**s) for s in d.get("sources") or []]
        return cls(
            claim_id=d["claim_id"],
            claim_text=d["claim_text"],
            created_at=d["created_at"],
            task_id=d.get("task_id"),
            stage=d.get("stage"),
            sources=sources,
            confidence=d.get("confidence", "medium"),
            verified=bool(d.get("verified", False)),
            artifact_id=d.get("artifact_id"),
            model=d.get("model"),
            prompt_hash=d.get("prompt_hash"),
        )

    def has_source(self) -> bool:
        return bool(self.sources)
