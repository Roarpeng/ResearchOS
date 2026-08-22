"""crawl.fetch SSRF-guard tests (docs/mcp/03 + docs/mcp/07)."""

from __future__ import annotations

import pytest

from tools.browser.crawl import fetch


def test_private_and_metadata_urls_rejected_even_offline() -> None:
    for url in (
        "http://127.0.0.1:9000/admin",
        "http://localhost/x",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.1.2.3/intranet",
        "file:///etc/passwd",
    ):
        res = fetch(url)
        assert res["ok"] is False
        assert res["error"] in {"ssrf_blocked", "scheme_denied"}


def test_offline_stub_is_marked_and_capped() -> None:
    res = fetch("https://example.com/doc", max_chars=200)
    assert res["ok"] is True
    assert res["stub"] is True
    assert len(res["text"]) <= 200
    assert "network_egress_disabled" in res["warnings"]


def test_real_fetch_rejects_oversize(monkeypatch: pytest.MonkeyPatch) -> None:
    """When egress is enabled, response size caps abort the stream."""
    monkeypatch.setenv("CRAWL_ALLOW_NETWORK", "1")
    import tools.browser.crawl as crawl_mod

    class FakeResp:
        url = "https://example.com/big"
        status_code = 200
        encoding = "utf-8"

        def raise_for_status(self) -> None:
            return None

        def iter_bytes(self):  # noqa: ANN202
            for _ in range(16):
                yield b"x" * 1024

        def __enter__(self):
            return self

        def __exit__(self, *a) -> None:
            return False

    class FakeClient:
        def __init__(self, *a, **k) -> None:
            return None

        def __enter__(self):
            return self

        def __exit__(self, *a) -> None:
            return False

        def stream(self, method, url):  # noqa: ANN202
            return FakeResp()

    monkeypatch.setattr(crawl_mod.httpx, "Client", FakeClient)
    monkeypatch.setattr(
        crawl_mod, "validate_url", lambda u, **k: ["93.184.216.34"]
    )
    monkeypatch.setattr(
        crawl_mod, "_MAX_BYTES_DEFAULT", 4096, raising=False
    )
    res = fetch("https://example.com/big")
    assert res["ok"] is False
    assert res["error"] == "payload_too_large"


def test_real_fetch_success_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRAWL_ALLOW_NETWORK", "1")
    import tools.browser.crawl as crawl_mod

    html = b"<html><head><title>Doc</title></head><body><p>hello world</p></body></html>"

    class FakeResp:
        url = "https://example.com/doc"
        status_code = 200
        encoding = "utf-8"

        def raise_for_status(self) -> None:
            return None

        def iter_bytes(self):  # noqa: ANN202
            yield html

        def __enter__(self):
            return self

        def __exit__(self, *a) -> None:
            return False

    class FakeClient:
        def __init__(self, *a, **k) -> None:
            return None

        def __enter__(self):
            return self

        def __exit__(self, *a) -> None:
            return False

        def stream(self, method, url):  # noqa: ANN202
            return FakeResp()

    monkeypatch.setattr(crawl_mod.httpx, "Client", FakeClient)
    monkeypatch.setattr(
        crawl_mod, "validate_url", lambda u, **k: ["93.184.216.34"]
    )
    res = fetch("https://example.com/doc")
    assert res["ok"] is True
    assert res["stub"] is False
    assert res["title"] == "Doc"
    assert "hello world" in res["text"]
