"""Vault end-to-end smoke: ingest a small folder locally (no Docker), then search.

Usage: uv run python scripts/smoke_vault.py
Expects local fallbacks: pseudo-embeddings + in-memory BM25 + local vector/graph.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from tools.vault import core


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="vault-smoke-"))
    (root / "wheat.md").write_text(
        "# Wheat\nWheat grain yield responded significantly to nitrogen fertilizer rate.\n",
        encoding="utf-8",
    )
    (root / "rice.txt").write_text(
        "Rice drought tolerance was improved by the OsNAC transcription factor.\n",
        encoding="utf-8",
    )
    (root / "ignore.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    print("root:", root)
    res = core.ingest(root)
    print(
        f"first: scanned={res.scanned} ingested={res.ingested} "
        f"failed={res.failed} skipped_unchanged={res.skipped_unchanged} "
        f"skipped_unsupported={res.skipped_unsupported}"
    )
    for d in res.details:
        print("  ", d)

    res2 = core.ingest(root)
    print(
        f"re-run: ingested={res2.ingested} failed={res2.failed} "
        f"skipped_unchanged={res2.skipped_unchanged}"
    )

    from knowledge.pipeline import KnowledgePipeline

    hit = KnowledgePipeline().search("nitrogen fertilizer wheat", top_k=3)
    print("SEARCH:", hit)

    if res.ingested < 2 or res.failed != 0 or res2.skipped_unchanged < 2:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
