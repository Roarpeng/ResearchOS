"""crawl.fetch — SSRF-guarded page fetch with offline stub fallback.

Per docs/mcp/03-browser-and-crawl.md and docs/mcp/07 (SSRF + quotas):

- Every URL passes :func:`tools.security.validate_url` first — private /
  loopback / metadata hosts are rejected even when network egress is off.
- Real HTTP fetch only when ``CRAWL_ALLOW_NETWORK`` is truthy; otherwise a
  clearly-marked stub payload keeps tests and air-gapped installs deterministic.
- Real fetches enforce size/time caps, limited redirects and record the
  redirect chain for audit.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from tools.security import SecurityError, redact_secrets, validate_url

_MAX_BYTES_DEFAULT = 512 * 1024


def _network_enabled() -> bool:
    return os.getenv("CRAWL_ALLOW_NETWORK", "").strip().lower() in {"1", "true", "yes", "on"}


def _egress_allowlist() -> tuple[str, ...] | None:
    raw = os.getenv("CRAWL_EGRESS_ALLOWLIST", "").strip()
    if not raw:
        return None
    return tuple(d.strip().lower() for d in raw.split(",") if d.strip())


def _stub_payload(url: str, max_chars: int) -> dict[str, Any]:
    parsed = urlparse(url)
    host = parsed.netloc or "example.com"
    path = parsed.path or "/"
    title = f"Stub page: {host}{path}"
    text = (
        f"This is a placeholder crawl body for {url}.\n"
        f"Host: {host}\n"
        f"Retrieved at: {datetime.now(timezone.utc).isoformat()}\n"
        "Network egress disabled; set CRAWL_ALLOW_NETWORK=1 to enable real fetches.\n"
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
        "warnings": ["network_egress_disabled"],
    }


def _html_to_text(html: str) -> str:
    import re

    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _real_fetch(
    url: str,
    *,
    max_chars: int,
    timeout: float,
    max_bytes: int,
) -> dict[str, Any]:
    resolved_ips = validate_url(url, egress_allowlist=_egress_allowlist())
    chain: list[str] = [url]
    with httpx.Client(
        follow_redirects=True,
        max_redirects=3,
        timeout=timeout,
        headers={"User-Agent": "ResearchOS-Crawl/0.1"},
    ) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            final = str(resp.url)
            if final != url:
                validate_url(final, egress_allowlist=_egress_allowlist())
                chain.append(final)
            chunks: list[bytes] = []
            received = 0
            for chunk in resp.iter_bytes():
                received += len(chunk)
                if received > max_bytes:
                    raise SecurityError("payload_too_large", f"response exceeds {max_bytes} bytes")
                chunks.append(chunk)
            html_bytes = b"".join(chunks)
    html = html_bytes.decode(resp.encoding or "utf-8", errors="replace")
    title_match = _first_title(html)
    return {
        "ok": True,
        "url": url,
        "final_url": final,
        "title": title_match or "",
        "text": redact_secrets(_html_to_text(html))[:max_chars],
        "html": html[:max_chars],
        "status_code": resp.status_code,
        "bytes": len(html_bytes),
        "resolved_ips": resolved_ips[:8],
        "redirect_chain": chain,
        "stub": False,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


def _first_title(html: str) -> str:
    import re

    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    return match.group(1).strip() if match else ""


def fetch(url: str, *, max_chars: int = 4000, timeout: float = 10.0) -> dict[str, Any]:
    """Fetch a page (SSRF-guarded); falls back to stub when egress is off."""
    try:
        validate_url(url, resolve_dns=_network_enabled(), egress_allowlist=_egress_allowlist())
    except SecurityError as exc:
        return {
            "ok": False,
            "url": url,
            "error": exc.code,
            "detail": exc.detail,
            "stub": False,
        }
    if not _network_enabled():
        return _stub_payload(url, max_chars=max_chars)
    try:
        return _real_fetch(url, max_chars=max_chars, timeout=timeout, max_bytes=_MAX_BYTES_DEFAULT)
    except SecurityError as exc:
        return {"ok": False, "url": url, "error": exc.code, "detail": exc.detail}
    except Exception as exc:  # noqa: BLE001 — network layer failures degrade cleanly
        return {
            "ok": False,
            "url": url,
            "error": "fetch_failed",
            "detail": redact_secrets(str(exc))[:300],
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
