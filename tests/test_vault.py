"""Vault core unit tests (pure scan/hash/manifest — no data plane required)."""

from __future__ import annotations

from pathlib import Path

from tools.vault import core


def test_sha256_stable(tmp_path: Path) -> None:
    p = tmp_path / "a.txt"
    p.write_text("abc", encoding="utf-8")
    digest = core.sha256_file(p)
    assert digest == core.sha256_file(p)
    assert digest.startswith("sha256:")


def test_scan_flags_support_and_skips_hidden(tmp_path: Path) -> None:
    (tmp_path / "note.md").write_text("# hello", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n")
    hidden = tmp_path / ".hidden"
    hidden.mkdir()
    (hidden / "secret.txt").write_text("x", encoding="utf-8")

    entries = core.scan(tmp_path)
    names = {Path(e.path).name for e in entries}
    assert names == {"note.md", "image.png"}
    by_name = {Path(e.path).name: e for e in entries}
    assert by_name["note.md"].supported is True
    assert by_name["image.png"].supported is False


def test_manifest_roundtrip(tmp_path: Path) -> None:
    manifest = core.VaultManifest(tmp_path, manifest_path=tmp_path / "m.json")
    manifest.set("a.pdf", {"hash": "sha256:x", "status": "ready"})
    manifest.save()

    reloaded = core.VaultManifest(tmp_path, manifest_path=tmp_path / "m.json")
    assert reloaded.get("a.pdf") == {"hash": "sha256:x", "status": "ready"}
