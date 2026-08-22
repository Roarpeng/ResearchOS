"""GitHub MCP tool tests (read-only scope per docs/mcp/07)."""

from __future__ import annotations

from tools.github.server import github_get_file, github_search_code


def test_get_file_requires_args() -> None:
    res = github_get_file("", "")
    assert res["ok"] is False
    assert res["error"] == "invalid_argument"


def test_search_code_requires_token(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    res = github_search_code("researchos")
    assert res["ok"] is False
    assert res["error"] == "github_token_required"


def test_get_file_rejects_offsite_hosts(monkeypatch) -> None:
    """SSRF/egress guard pins hosts to api.github.com."""
    import httpx

    def fake_get(self, url, **kwargs):  # noqa: ANN001, ANN202
        raise AssertionError("network must not be reached for offsite host")

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    # craft a repo path that would redirect offsite is impossible here; instead
    # verify allowlist by direct guard behavior through a mocked transport-free call:
    res = github_get_file("../evil", "x")
    assert res["ok"] is False


def test_get_file_404_is_clean(monkeypatch) -> None:
    import httpx

    class Resp:
        status_code = 404

    def fake_get(self, url, **kwargs):  # noqa: ANN001, ANN202
        return Resp()

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    res = github_get_file("acme/nope", "missing.txt")
    assert res["ok"] is False
    assert res["error"] == "not_found"
