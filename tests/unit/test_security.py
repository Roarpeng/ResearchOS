"""Tool security layer tests (docs/mcp/07-tool-security-and-permissions.md)."""

from __future__ import annotations

import pytest

from tools.security import (
    AuditSink,
    QuotaTracker,
    SecurityError,
    assert_role_allowed,
    make_audit_record,
    redact_secrets,
    required_scopes,
    role_can,
    side_effect_level,
    validate_url,
)


# --- Scope matrix ----------------------------------------------------------


def test_research_cannot_write_vector_or_kg_by_default() -> None:
    assert role_can("research", "vector.upsert") is False
    assert role_can("research", "kg.write") is False
    assert role_can("research", "search.web") is True


def test_memory_can_write_but_not_export() -> None:
    assert role_can("memory", "kg.write") is True
    assert role_can("memory", "report.export") is False


def test_task_grant_enables_temporary_scope() -> None:
    assert role_can("research", "kg.write") is False
    assert role_can("research", "kg.write", granted={"kg:write"}) is True


def test_unknown_tool_defaults_allowed_l0() -> None:
    assert required_scopes("plc.st.parse") == ()
    assert side_effect_level("plc.st.parse") == "L0"
    assert role_can("reviewer", "plc.st.parse") is True


def test_assert_role_allowed_raises() -> None:
    with pytest.raises(SecurityError) as excinfo:
        assert_role_allowed("writer", "kg.write")
    assert excinfo.value.code == "scope_denied"


# --- SSRF -------------------------------------------------------------------


def test_ssrf_blocks_private_loopback_and_metadata() -> None:
    for url in (
        "http://127.0.0.1:8000/admin",
        "http://localhost/secret",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/x",
        "http://10.0.0.5/internal",
        "http://192.168.1.10/router",
        "https://metadata.google.internal/computeMetadata/v1/",
    ):
        with pytest.raises(SecurityError):
            validate_url(url)


def test_ssrf_blocks_non_http_schemes() -> None:
    with pytest.raises(SecurityError):
        validate_url("file:///etc/passwd")
    with pytest.raises(SecurityError):
        validate_url("ftp://example.com/file")


def test_public_domain_resolves_and_returns_ips() -> None:
    # example.com has A records and is safe to resolve in CI sandboxes.
    try:
        ips = validate_url("https://example.com/doc")
    except SecurityError as exc:
        if exc.code == "dns_failed":
            pytest.skip("no DNS available in sandbox")
        raise
    assert all(not ip.startswith(("127.", "10.", "192.168.")) for ip in ips)


def test_egress_allowlist() -> None:
    with pytest.raises(SecurityError) as excinfo:
        validate_url(
            "https://example.com/x",
            resolve_dns=False,
            egress_allowlist=("siemens.com",),
        )
    assert excinfo.value.code == "egress_denied"

    ips = validate_url(
        "https://docs.siemens.com/x",
        resolve_dns=False,
        egress_allowlist=("siemens.com",),
    )
    assert ips == []


# --- Side-effect levels ------------------------------------------------------


def test_side_effect_levels_match_doc() -> None:
    assert side_effect_level("knowledge.retrieve") == "L0"
    assert side_effect_level("crawl.fetch") == "L1"
    assert side_effect_level("vector.upsert") == "L2"
    assert side_effect_level("report.export") == "L3"
    assert side_effect_level("kg.cypher_raw") == "L4"


# --- Quotas ------------------------------------------------------------------


def test_quota_exceeded_raises_with_code() -> None:
    tracker = QuotaTracker(limits={"ws1|u1|crawl": 2})
    tracker.check_and_consume("ws1|u1|crawl")
    tracker.check_and_consume("ws1|u1|crawl")
    with pytest.raises(SecurityError) as excinfo:
        tracker.check_and_consume("ws1|u1|crawl")
    assert excinfo.value.code == "quota_exceeded"


def test_unlimited_key_returns_negative_remaining() -> None:
    tracker = QuotaTracker()
    assert tracker.check_and_consume("anything") == -1


# --- Audit -------------------------------------------------------------------


def test_audit_record_has_digest_not_payload() -> None:
    rec = make_audit_record(
        tool_name="vector.upsert",
        agent_name="memory",
        status="ok",
        workspace_id="ws_1",
        task_id="task_9",
        params={"chunks": [{"text": "secret body"}]},
        latency_ms=12,
        artifact_ids=["art_1"],
    )
    blob = str(rec)
    assert rec["params_digest"] and len(rec["params_digest"]) == 16
    assert "secret body" not in blob
    assert rec["side_effect_level"] == "L2"
    sink = AuditSink()
    sink.write(rec)
    assert sink.by_task("task_9")[0]["tool_name"] == "vector.upsert"


def test_redact_secrets_masks_auth_headers() -> None:
    text = "Authorization: Bearer abc.def.ghi; api_key=sk-123; token=xyz"
    out = redact_secrets(text)
    assert "abc.def.ghi" not in out
    assert "sk-123" not in out
    assert "[REDACTED]" in out
