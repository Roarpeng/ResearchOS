"""Tool-layer security primitives (docs/mcp/07-tool-security-and-permissions.md).

Foundations every MCP server and the Runtime can share:

- Scope directory + per-agent-role default allowlists
- SSRF guard for outbound URLs (scheme/private-net/metadata/DNS re-check)
- Side-effect level classification (L0–L4)
- Workspace/user/tool quota metering (process-local)
- Structured audit records with digests instead of raw payloads
- Output redaction for secrets/headers

Design constraint: stdlib-only so any tool server can import it.
"""

from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

SECURITY_ERROR = "security_violation"


class SecurityError(Exception):
    """Raised when a tool call violates the security policy."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------------------
# Scope directory + role allowlists
# ---------------------------------------------------------------------------

KNOWN_SCOPES: frozenset[str] = frozenset(
    {
        "search:read",
        "crawl:fetch",
        "crawl:site",
        "browser:interactive",
        "parser:read",
        "parser:write",
        "documents:read",
        "documents:write",
        "vector:read",
        "vector:write",
        "kg:read",
        "kg:write",
        "knowledge:retrieve",
        "report:preview",
        "report:export",
        "github:read",
        "github:write",
        "admin:mcp",
    }
)

# Tool name → required scopes (any-of). Unlisted tools default to L0/read.
TOOL_SCOPES: dict[str, tuple[str, ...]] = {
    "search.web": ("search:read",),
    "search.news": ("search:read",),
    "crawl.fetch": ("crawl:fetch",),
    "crawl.site": ("crawl:site",),
    "browser.open": ("browser:interactive",),
    "documents.register": ("documents:read",),
    "documents.upload": ("documents:write",),
    "documents.get": ("documents:read",),
    "documents.list": ("documents:read",),
    "vector.search": ("vector:read",),
    "vector.embed": ("vector:read",),
    "vector.upsert": ("vector:write",),
    "vector.delete": ("vector:write",),
    "kg.query": ("kg:read",),
    "kg.write": ("kg:write",),
    "kg.upsert_entities": ("kg:write",),
    "knowledge.retrieve": ("knowledge:retrieve",),
    "fulltext.search": ("kg:read",),
    "knowledge.ingest_status": ("documents:read",),
    "report.preview": ("report:preview",),
    "report.validate_citations": ("report:preview",),
    "report.list_templates": ("report:preview",),
    "report.export": ("report:export",),
    "github.get_file": ("github:read",),
    "github.search_code": ("github:read",),
}

# Default agent role profiles from docs/mcp/07 §Agent 默认画像.
ROLE_ALLOWLISTS: dict[str, frozenset[str]] = {
    "planner": frozenset({"search:read", "knowledge:retrieve"}),
    "research": frozenset(
        {
            "search:read",
            "crawl:fetch",
            "browser:interactive",
            "parser:read",
            "parser:write",
            "documents:write",
            "knowledge:retrieve",
            "documents:read",
            "vector:read",
        }
    ),
    "memory": frozenset(
        {
            "kg:read",
            "kg:write",
            "vector:read",
            "vector:write",
            "parser:read",
            "parser:write",
            "documents:read",
            "documents:write",
            "knowledge:retrieve",
        }
    ),
    "writer": frozenset(
        {"knowledge:retrieve", "documents:read", "report:preview", "report:export"}
    ),
    "reviewer": frozenset({"knowledge:retrieve", "report:preview"}),
    "supervisor": frozenset({"knowledge:retrieve"}),
}


def required_scopes(tool_name: str) -> tuple[str, ...]:
    return TOOL_SCOPES.get(tool_name, ())


def role_can(tool_role: str, tool_name: str, *, granted: set[str] | None = None) -> bool:
    """True when role's allowlist (plus explicit task grants) covers the tool."""
    needed = required_scopes(tool_name)
    if not needed:
        return True
    allowed = ROLE_ALLOWLISTS.get((tool_role or "").strip().lower())
    extra = granted or set()
    return any(scope in allowed or scope in extra for scope in needed)


def assert_role_allowed(
    tool_role: str, tool_name: str, *, granted: set[str] | None = None
) -> None:
    if not role_can(tool_role, tool_name, granted=granted):
        raise SecurityError(
            "scope_denied",
            f"role={tool_role!r} lacks required scopes {required_scopes(tool_name)} for {tool_name}",
        )


# ---------------------------------------------------------------------------
# Side-effect classification
# ---------------------------------------------------------------------------

SIDE_EFFECT_LEVELS: dict[str, str] = {
    "crawl.fetch": "L1",
    "crawl.site": "L1",
    "browser.open": "L1",
    "documents.upload": "L2",
    "vector.upsert": "L2",
    "vector.delete": "L3",
    "kg.write": "L2",
    "kg.upsert_entities": "L2",
    "report.export": "L3",
    "github.apply_patch": "L3",
    "kg.cypher_raw": "L4",
}


def side_effect_level(tool_name: str) -> str:
    return SIDE_EFFECT_LEVELS.get(tool_name, "L0")


# ---------------------------------------------------------------------------
# SSRF guard
# ---------------------------------------------------------------------------

_METADATA_HOSTS = {"169.254.169.254", "metadata.google.internal", "100.100.100.200"}
_MAX_URL_LEN = 2048


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_url(
    raw_url: str,
    *,
    egress_allowlist: tuple[str, ...] | None = None,
    resolve_dns: bool = True,
) -> list[str]:
    """Validate an outbound URL; return resolved IPs (empty when unresolved).

    Raises SecurityError on scheme/host/IP violations. When ``resolve_dns`` is
    true the host is resolved and every returned address is re-checked, which
    also gives callers the pinned IPs to connect to (anti DNS-rebinding).
    """
    url = (raw_url or "").strip()
    if not url:
        raise SecurityError("invalid_url", "empty url")
    if len(url) > _MAX_URL_LEN:
        raise SecurityError("invalid_url", "url too long")
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"}:
        raise SecurityError("scheme_denied", f"scheme {parts.scheme!r} not allowed")
    host = parts.hostname or ""
    if not host:
        raise SecurityError("invalid_url", "missing host")
    if host.lower() in _METADATA_HOSTS:
        raise SecurityError("ssrf_blocked", "cloud metadata host denied")

    if egress_allowlist:
        lowered = host.lower()
        if not any(lowered == d or lowered.endswith("." + d) for d in egress_allowlist):
            raise SecurityError("egress_denied", f"host {host!r} outside egress allowlist")

    if not resolve_dns:
        return []

    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as exc:
        raise SecurityError("dns_failed", f"cannot resolve {host!r}: {exc}") from exc

    ips: list[str] = []
    for info in infos:
        addr = info[4][0]
        if addr in ips:
            continue
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if _is_blocked_ip(ip):
            raise SecurityError("ssrf_blocked", f"{host} resolves to blocked address {addr}")
        ips.append(addr)
    if not ips:
        raise SecurityError("dns_failed", f"no addresses resolved for {host!r}")
    return ips


# ---------------------------------------------------------------------------
# Quotas
# ---------------------------------------------------------------------------


@dataclass
class QuotaTracker:
    """Process-local daily quotas keyed by (workspace_id, actor, bucket)."""

    limits: dict[str, int] = field(default_factory=dict)
    _used: dict[tuple[str, str], int] = field(default_factory=dict)
    _day: str = field(default="")

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def check_and_consume(self, key: str, amount: int = 1) -> int:
        """Consume quota; return remaining. Raises on exhaustion."""
        today = self._today()
        if today != self._day:
            self._day = today
            self._used.clear()
        used_key = (key, today)
        limit = self.limits.get(key)
        current = self._used.get(used_key, 0)
        if limit is not None and current + amount > limit:
            raise SecurityError(
                "quota_exceeded",
                f"{key}: {current + amount}/{limit} exceeds daily quota",
            )
        self._used[used_key] = current + amount
        return (limit - current - amount) if limit is not None else -1


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def make_audit_record(
    *,
    tool_name: str,
    agent_name: str,
    status: str,
    workspace_id: str = "",
    task_id: str = "",
    actor_user_id: str = "",
    params: dict[str, Any] | None = None,
    error_code: str = "",
    latency_ms: int = 0,
    artifact_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Structured audit entry; never stores raw document bodies."""
    digest = ""
    if params:
        blob = repr(sorted(params.items())).encode("utf-8", "replace")
        digest = hashlib.sha256(blob).hexdigest()[:16]
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor_user_id": actor_user_id,
        "agent_name": agent_name,
        "workspace_id": workspace_id,
        "task_id": task_id,
        "tool_name": tool_name,
        "side_effect_level": side_effect_level(tool_name),
        "params_digest": digest,
        "status": status,
        "error_code": error_code,
        "latency_ms": latency_ms,
        "artifact_ids": list(artifact_ids or []),
    }


class AuditSink:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def write(self, record: dict[str, Any]) -> None:
        self.records.append(record)

    def by_task(self, task_id: str) -> list[dict[str, Any]]:
        return [r for r in self.records if r.get("task_id") == task_id]


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*)[^\r\n]+"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)\S+"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(token\s*[:=]\s*)[A-Za-z0-9._\-]+"),
)


def redact_secrets(text: str) -> str:
    out = text or ""
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub(lambda m: (m.group(1) or "") + "[REDACTED]", out)
    return out


__all__ = [
    "SECURITY_ERROR",
    "AuditSink",
    "KNOWN_SCOPES",
    "ROLE_ALLOWLISTS",
    "QuotaTracker",
    "SecurityError",
    "TOOL_SCOPES",
    "assert_role_allowed",
    "make_audit_record",
    "redact_secrets",
    "required_scopes",
    "role_can",
    "side_effect_level",
    "validate_url",
]


def _now_monotonic() -> float:
    return time.monotonic()
