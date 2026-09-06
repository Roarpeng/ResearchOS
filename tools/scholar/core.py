"""Scholar core: lookup-only citation metadata + phantom-citation scan.

Network access uses httpx against public Crossref/OpenAlex APIs; unit tests stay
hermetic by injecting a resolver or testing pure normalization/regex functions.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable

import httpx

logger = logging.getLogger("researchos.tools.scholar")

DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"']+", re.IGNORECASE)
_HEADERS = {"User-Agent": "ResearchOS-scholar/0.1 (mailto:dev@example.com)"}

ResolveFn = Callable[[str], dict[str, Any] | None]


def extract_dois(text: str) -> list[str]:
    return [m.group(0).rstrip(".,;:)]") for m in DOI_RE.finditer(text or "")]


def _normalize_crossref(item: dict[str, Any]) -> dict[str, Any]:
    title = (item.get("title") or [""])[0]
    authors: list[str] = []
    for a in item.get("author") or []:
        fam = a.get("family", "")
        giv = a.get("given", "")
        authors.append(f"{giv} {fam}".strip() or fam)
    year = None
    for key in ("published-print", "published-online", "issued", "created"):
        dp = (item.get(key) or {}).get("date-parts") or []
        if dp and dp[0] and dp[0][0]:
            year = dp[0][0]
            break
    containers = item.get("container-title") or []
    journal = containers[0] if containers else None
    doi = item.get("DOI")
    return {
        "doi": doi,
        "title": title,
        "authors": authors,
        "journal": journal,
        "year": year,
        "publisher": item.get("publisher"),
        "url": item.get("URL") or (f"https://doi.org/{doi}" if doi else None),
    }


def _resolve_crossref(doi: str, client: httpx.Client) -> dict[str, Any] | None:
    resp = client.get(
        f"https://api.crossref.org/works/{doi}", headers=_HEADERS, timeout=20.0
    )
    if resp.status_code == 200:
        return _normalize_crossref(resp.json().get("message") or {})
    return None


def _resolve_openalex(doi: str, client: httpx.Client) -> dict[str, Any] | None:
    resp = client.get(
        f"https://api.openalex.org/works/doi:{doi}", headers=_HEADERS, timeout=20.0
    )
    if resp.status_code != 200:
        return None
    w = resp.json()
    authors = [
        (a.get("author") or {}).get("display_name", "")
        for a in w.get("authorships") or []
        if a.get("author")
    ]
    loc = w.get("primary_location") or {}
    source = loc.get("source") or {}
    return {
        "doi": w.get("doi"),
        "title": w.get("title"),
        "authors": [a for a in authors if a],
        "journal": source.get("display_name"),
        "year": w.get("publication_year"),
        "publisher": None,
        "url": f"https://doi.org/{w['doi']}" if w.get("doi") else None,
    }


def resolve(doi: str) -> dict[str, Any] | None:
    doi = doi.strip()
    with httpx.Client() as client:
        item = _resolve_crossref(doi, client)
        if item is not None:
            return item
        return _resolve_openalex(doi, client)


def lookup(query: str, rows: int = 10) -> list[dict[str, Any]]:
    with httpx.Client() as client:
        resp = client.get(
            "https://api.crossref.org/works",
            params={"query.bibliographic": query, "rows": max(1, min(rows, 50))},
            headers=_HEADERS,
            timeout=20.0,
        )
        if resp.status_code != 200:
            return []
        items = (resp.json().get("message") or {}).get("items") or []
        return [_normalize_crossref(i) for i in items]


def verify(
    text_or_dois: str | list[str],
    resolver: ResolveFn | None = None,
) -> dict[str, Any]:
    """Scan citations; return resolved + phantom (unresolvable) lists."""
    fn = resolver or resolve
    if isinstance(text_or_dois, str):
        dois = extract_dois(text_or_dois)
    else:
        dois = [str(d) for d in text_or_dois]

    resolved: list[dict[str, Any]] = []
    phantom: list[dict[str, str]] = []
    for d in dois:
        try:
            item = fn(d)
        except Exception as exc:  # noqa: BLE001
            phantom.append({"doi": d, "reason": str(exc)})
            continue
        if item and item.get("doi"):
            resolved.append(item)
        else:
            phantom.append({"doi": d, "reason": "unresolvable"})

    return {
        "total": len(dois),
        "resolved": len(resolved),
        "phantom": len(phantom),
        "items": resolved,
        "phantom_items": phantom,
    }
