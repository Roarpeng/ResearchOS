"""Knowledge worker entrypoint (batch ingest jobs)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

from knowledge.pipeline import KnowledgePipeline
from researchos_shared import configure_logging

logger = logging.getLogger("researchos.knowledge.worker")


def process_paths(paths: Iterable[str | Path], *, workspace_id: str | None = None) -> list[dict]:
    pipeline = KnowledgePipeline()
    results = []
    for path in paths:
        p = Path(path)
        logger.info("ingest start path=%s", p)
        result = pipeline.ingest_file(p, workspace_id=workspace_id)
        logger.info(
            "ingest done doc_id=%s status=%s chunks=%s",
            result.doc_id,
            result.status,
            result.chunk_count,
        )
        results.append(result.model_dump(mode="json"))
    return results


def main(argv: list[str] | None = None) -> int:
    import argparse

    configure_logging()
    parser = argparse.ArgumentParser(description="ResearchOS knowledge worker")
    parser.add_argument("paths", nargs="+", help="Files to ingest")
    parser.add_argument("--workspace", default=None)
    args = parser.parse_args(argv)
    process_paths(args.paths, workspace_id=args.workspace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
