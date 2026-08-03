"""Stub crawl.fetch — returns placeholder HTML/text without real network."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse


def fetch(url: str, *, max_chars: int = 4000) -> dict[str, Any]:
    """Return placeholder crawl payload for a URL."""
    parsed = urlparse(url)
    host = parsed.netloc or "example.com"
    path = parsed.path or "/"
    title = f"Stub page: {host}{path}"
    text = (
        f"This is a placeholder crawl body for {url}.\n"
        f"Host: {host}\n"
        f"Retrieved at: {datetime.now(timezone.utc).isoformat()}\n"
        "Real browser rendering is not enabled in this MVP stub.\n"
    )
    html = (
        f"<!DOCTYPE html><html><head><title>{title}</title></head>"
        f"<body><h1>{title}</h1><p>{text}</p></body></html>"
    )
    if len(text) > max_chars:
        text = text[: max_chars - 3] + "..."
    if len(html) > max_chars:
        html = html[: max_chars - 3] + "..."

    return {
        "ok": True,
        "url": url,
        "title": title,
        "text": text,
        "html": html,
        "status_code": 200,
        "stub": True,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }
