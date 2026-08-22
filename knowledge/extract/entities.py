"""Rule/regex MVP entity & relation extraction."""

from __future__ import annotations

import re
from typing import Iterable

from knowledge.models import Chunk, Entity, Relation

# Product-like model tokens: RS-200, ACME-X1, ABC123
_PRODUCT_RE = re.compile(
    r"\b([A-Z]{1,6}(?:-[A-Z0-9]{1,8}|\d{2,5})(?:-[A-Z0-9]{1,6})?)\b"
)
_SPEC_RE = re.compile(
    r"(额定扭矩|峰值扭矩|扭矩|torque|功率|power|电压|voltage|转速|speed)"
    r"\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)\s*(Nm|N·m|W|kW|V|rpm|RPM)?",
    re.I,
)
_COMPANY_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9&\-]{1,20}(?:\s+(?:Inc|Ltd|LLC|Corp|Company|公司))?)\b"
)
_COMPARE_RE = re.compile(r"(对比|比较|vs\.?|versus|差异|竞品)", re.I)
_PAIN_RE = re.compile(r"(痛点|差评|不好|故障|噪音|难用|defect|issue|problem)", re.I)

_ENTITY_TYPES = {
    "Product",
    "Feature",
    "Specification",
    "PainPoint",
    "Review",
    "News",
    "Company",
    "Patent",
    "Document",
    "Chunk",
    "Standard",
    "Version",
}

_RELATION_TYPES = {
    "HAS_FEATURE",
    "COMPARES",
    "REFERENCES",
    "UPDATED_BY",
    "PRODUCED_BY",
}


def _canon(entity_type: str, name: str) -> str:
    key = re.sub(r"\s+", "_", name.strip().lower())
    return f"{entity_type.lower()}:{key}"


def extract_from_text(
    text: str,
    *,
    chunk_id: str | None = None,
    section_type: str | None = None,
    doc_id: str | None = None,
) -> tuple[list[Entity], list[Relation]]:
    entities: dict[str, Entity] = {}
    relations: list[Relation] = []

    products: list[Entity] = []
    for match in _PRODUCT_RE.finditer(text):
        name = match.group(1)
        # Filter common false positives (years, short all-digit)
        if name.isdigit() and len(name) == 4:
            continue
        ent = Entity(
            type="Product",
            canonical_key=_canon("Product", name),
            name=name,
            properties={"chunk_id": chunk_id} if chunk_id else {},
        )
        entities[ent.canonical_key] = ent
        products.append(ent)

    for match in _SPEC_RE.finditer(text):
        feature = match.group(1)
        value = match.group(2)
        unit = match.group(3) or ""
        feat = Entity(
            type="Feature",
            canonical_key=_canon("Feature", feature),
            name=feature,
            properties={},
        )
        spec = Entity(
            type="Specification",
            canonical_key=_canon("Specification", f"{feature}_{value}_{unit}"),
            name=f"{feature}={value}{unit}",
            properties={"value": value, "unit": unit, "feature": feature},
        )
        entities[feat.canonical_key] = feat
        entities[spec.canonical_key] = spec
        for product in products:
            relations.append(
                Relation(
                    type="HAS_FEATURE",
                    from_key=product.canonical_key,
                    to_key=spec.canonical_key,
                    from_type="Product",
                    to_type="Specification",
                    properties={
                        "value": value,
                        "unit": unit,
                        "chunk_id": chunk_id,
                        "feature": feature,
                    },
                )
            )
            relations.append(
                Relation(
                    type="REFERENCES",
                    from_key=spec.canonical_key,
                    to_key=chunk_id or "chunk:unknown",
                    from_type="Specification",
                    to_type="Chunk",
                    properties={"chunk_id": chunk_id},
                )
            )

    if _PAIN_RE.search(text) or section_type == "review":
        snippet = text.strip()[:80]
        pain = Entity(
            type="PainPoint",
            canonical_key=_canon("PainPoint", snippet[:40] or "pain"),
            name=snippet or "pain_point",
            properties={"chunk_id": chunk_id},
        )
        entities[pain.canonical_key] = pain
        for product in products:
            relations.append(
                Relation(
                    type="REFERENCES",
                    from_key=pain.canonical_key,
                    to_key=chunk_id or "chunk:unknown",
                    from_type="PainPoint",
                    to_type="Chunk",
                    properties={"chunk_id": chunk_id},
                )
            )

    if _COMPARE_RE.search(text) and len(products) >= 2:
        relations.append(
            Relation(
                type="COMPARES",
                from_key=products[0].canonical_key,
                to_key=products[1].canonical_key,
                from_type="Product",
                to_type="Product",
                properties={"chunk_id": chunk_id},
            )
        )

    # Light company heuristic only when near product mention
    if products:
        for match in _COMPANY_RE.finditer(text):
            name = match.group(1)
            if name in {p.name for p in products}:
                continue
            if len(name) < 3:
                continue
            company = Entity(
                type="Company",
                canonical_key=_canon("Company", name),
                name=name,
            )
            entities[company.canonical_key] = company
            relations.append(
                Relation(
                    type="PRODUCED_BY",
                    from_key=products[0].canonical_key,
                    to_key=company.canonical_key,
                    from_type="Product",
                    to_type="Company",
                    properties={"chunk_id": chunk_id},
                )
            )
            break

    # UPDATED_BY: research artifact (Product) -> source Document, when doc scope known.
    if products and doc_id:
        doc_key = f"document:{doc_id}"
        entities[doc_key] = Entity(
            type="Document",
            canonical_key=doc_key,
            name=doc_id,
            properties={},
        )
        for product in products:
            relations.append(
                Relation(
                    type="UPDATED_BY",
                    from_key=product.canonical_key,
                    to_key=doc_key,
                    from_type="Product",
                    to_type="Document",
                    properties={"chunk_id": chunk_id, "doc_id": doc_id},
                )
            )

    return list(entities.values()), relations


def extract_from_chunks(chunks: Iterable[Chunk]) -> tuple[list[Entity], list[Relation]]:
    entities: dict[str, Entity] = {}
    relations: list[Relation] = []
    for chunk in chunks:
        ents, rels = extract_from_text(
            chunk.text,
            chunk_id=chunk.chunk_id,
            section_type=chunk.section_type,
            doc_id=chunk.doc_id,
        )
        for e in ents:
            entities[e.canonical_key] = e
        relations.extend(rels)
    # Deduplicate relations loosely
    seen: set[tuple[str, str, str]] = set()
    unique_rels: list[Relation] = []
    for r in relations:
        key = (r.type, r.from_key, r.to_key)
        if key in seen:
            continue
        seen.add(key)
        unique_rels.append(r)
    return list(entities.values()), unique_rels
