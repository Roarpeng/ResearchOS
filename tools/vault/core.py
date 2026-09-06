"""Vault core: folder scan → SHA256 dedup → knowledge ingest (incremental, dependency-light).

Heavy imports (knowledge.pipeline / knowledge.settings) are lazy so that scan/hash/manifest
remain testable without a configured data plane.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("researchos.tools.vault")

SUPPORTED_EXTS = {
    ".pdf", ".docx", ".doc", ".md", ".markdown", ".txt", ".rst",
    ".csv", ".tsv", ".xlsx", ".xls", ".bib", ".ris", ".html", ".htm",
    ".ipynb", ".pptx",
}

_COMPLETED_STATUSES = {"ready", "ready_degraded", "ingested", "ok"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTS


@dataclass
class FileEntry:
    path: str
    size: int
    mtime: float
    supported: bool
    hash: str | None = None


def scan(root: str | Path) -> list[FileEntry]:
    root = Path(root)
    out: list[FileEntry] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        st = p.stat()
        out.append(
            FileEntry(
                path=str(p),
                size=st.st_size,
                mtime=st.st_mtime,
                supported=is_supported(p),
            )
        )
    return out


def _default_manifest_path() -> Path:
    from knowledge.settings import get_settings

    return Path(get_settings().objects_path) / "vault" / "manifest.json"


class VaultManifest:
    """Persist per-file (sha256, doc_id, status) to skip unchanged files."""

    def __init__(self, root: str | Path, manifest_path: Path | None = None) -> None:
        self.root = Path(root)
        self.path = manifest_path or _default_manifest_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict[str, Any]] = self._load()

    def _load(self) -> dict[str, dict[str, Any]]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                return {}
        return {}

    def save(self) -> None:
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def get(self, path: str) -> dict[str, Any] | None:
        return self._data.get(path)

    def set(self, path: str, entry: dict[str, Any]) -> None:
        self._data[path] = entry


@dataclass
class VaultResult:
    scanned: int = 0
    ingested: int = 0
    skipped_unchanged: int = 0
    skipped_unsupported: int = 0
    failed: int = 0
    details: list[dict[str, Any]] = field(default_factory=list)


def ingest(
    root: str | Path,
    workspace_id: str | None = None,
    pipeline: Any = None,
    manifest_path: Path | None = None,
) -> VaultResult:
    root = Path(root)
    manifest = VaultManifest(root, manifest_path=manifest_path)
    if pipeline is None:
        from knowledge.pipeline import KnowledgePipeline

        pipeline = KnowledgePipeline()

    res = VaultResult()
    for entry in scan(root):
        res.scanned += 1
        p = Path(entry.path)
        if not entry.supported:
            res.skipped_unsupported += 1
            continue
        try:
            digest = sha256_file(p)
        except Exception as exc:  # noqa: BLE001
            res.failed += 1
            res.details.append({"path": str(p), "error": str(exc)})
            continue
        prev = manifest.get(str(p))
        if prev and prev.get("hash") == digest and prev.get("status") in _COMPLETED_STATUSES:
            res.skipped_unchanged += 1
            continue
        try:
            out = pipeline.ingest_file(p, workspace_id=workspace_id, title=p.stem)
            status, doc_id = out.status, out.doc_id
        except Exception as exc:  # noqa: BLE001
            res.failed += 1
            manifest.set(str(p), {"hash": digest, "status": "failed", "error": str(exc),
                                  "mtime": entry.mtime})
            res.details.append({"path": str(p), "error": str(exc)})
            continue
        manifest.set(str(p), {"hash": digest, "doc_id": doc_id, "status": status,
                              "mtime": entry.mtime})
        res.ingested += 1
        res.details.append({"path": str(p), "doc_id": doc_id, "status": status})
    manifest.save()
    return res


class VaultWatcher:
    """Background polling watcher; ingests new/changed files every `interval` seconds."""

    def __init__(
        self,
        root: str | Path,
        workspace_id: str | None = None,
        interval: float = 5.0,
        pipeline: Any = None,
    ) -> None:
        self.root = Path(root)
        self.workspace_id = workspace_id
        self.interval = interval
        self.pipeline = pipeline
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> dict[str, Any]:
        if self._thread and self._thread.is_alive():
            return {"ok": True, "already_running": True}
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="vault-watcher", daemon=True)
        self._thread.start()
        return {"ok": True, "started": True, "interval_s": self.interval}

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        return {"ok": True}

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                ingest(self.root, workspace_id=self.workspace_id, pipeline=self.pipeline)
            except Exception as exc:  # noqa: BLE001
                logger.exception("vault watcher cycle failed: %s", exc)
            self._stop.wait(self.interval)


def append_note(root: str | Path, text: str, tag: str | None = None, subdir: str = "inbox") -> dict[str, Any]:
    """Quick capture: write a timestamped Markdown note into the research folder."""
    import datetime

    base = Path(root) / subdir
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    name = f"{stamp}-{tag}.md" if tag else f"{stamp}.md"
    path = base / name
    path.write_text(f"# {text}\n", encoding="utf-8")
    return {"path": str(path), "note": text, "tag": tag}


_CHAT_TS_RE = re.compile(r"^\s*(\d{1,2}:\d{2}(?::\d{2})?|\d{4}-\d{2}-\d{2}[ T]\d{1,2}:\d{2})")


def import_chat_transcript(
    root: str | Path,
    text: str,
    subdir: str = "chat",
) -> dict[str, Any]:
    """Split a chat transcript into per-turn Markdown notes (timestamp heuristic)."""
    base = Path(root) / subdir
    base.mkdir(parents=True, exist_ok=True)

    turns: list[tuple[str, str]] = []
    ts: str | None = None
    buf: list[str] = []
    for line in text.splitlines():
        m = _CHAT_TS_RE.match(line)
        if m:
            if ts is not None:
                turns.append((ts, "\n".join(buf).strip()))
            ts = m.group(1)
            buf = [line[len(m.group(0)) :].strip()]
        elif ts is not None:
            buf.append(line)
    if ts is not None:
        turns.append((ts, "\n".join(buf).strip()))

    notes: list[dict[str, Any]] = []
    for i, (stamp, body) in enumerate(turns, 1):
        path = base / f"turn-{i:03d}.md"
        path.write_text(f"# [{stamp}]\n\n{body}\n", encoding="utf-8")
        notes.append({"path": str(path), "timestamp": stamp, "text": body})
    return {"turns": len(notes), "notes": notes}
