"""Knowledge CLI: ingest / search."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint

from knowledge.pipeline import KnowledgePipeline
from knowledge.store import get_registry
from researchos_shared import configure_logging

app = typer.Typer(add_completion=False, no_args_is_help=True, help="ResearchOS Knowledge Engine")


@app.callback()
def _configure() -> None:
    configure_logging()


@app.command("ingest")
def ingest_cmd(
    path: Optional[Path] = typer.Argument(None, help="File to ingest"),
    text: Optional[str] = typer.Option(None, "--text", "-t", help="Inline text to ingest"),
    filename: str = typer.Option("document.md", "--filename", "-f"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w"),
    title: Optional[str] = typer.Option(None, "--title"),
) -> None:
    """Ingest a file or inline text into the three-channel knowledge index."""
    pipeline = KnowledgePipeline()
    if text is not None:
        result = pipeline.ingest_text(text, filename=filename, workspace_id=workspace, title=title)
    elif path is not None:
        if not path.exists():
            raise typer.BadParameter(f"file not found: {path}")
        result = pipeline.ingest_file(path, workspace_id=workspace, title=title)
    else:
        raise typer.BadParameter("provide PATH or --text")
    rprint(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


@app.command("demo")
def demo_cmd(
    query: str = typer.Option("RS-200 额定扭矩", "--query", "-q"),
    top_k: int = typer.Option(5, "--top-k", "-k"),
) -> None:
    """One-shot ingest sample doc then hybrid search (good local smoke demo)."""
    sample = """# Acme RS-200 Manual

## 参数

额定扭矩: 12 Nm
峰值扭矩: 36 Nm

RS-200 与 RS-100 对比时，RS-200 扭矩更高。

## 用户评价

装配困难，螺丝公差问题明显。
"""
    pipeline = KnowledgePipeline()
    ingested = pipeline.ingest_text(sample, filename="demo-rs200.md", title="RS-200 Demo")
    pack = pipeline.search(query, top_k=top_k)
    rprint(
        json.dumps(
            {"ingest": ingested.model_dump(mode="json"), "search": pack},
            ensure_ascii=False,
            indent=2,
        )
    )


@app.command("search")
def search_cmd(
    query: str = typer.Argument(..., help="Search query"),
    top_k: int = typer.Option(8, "--top-k", "-k"),
    model: Optional[str] = typer.Option(None, "--model", help="Filter by model token"),
) -> None:
    """Hybrid search (vector + BM25 + graph RRF) → Context Pack JSON."""
    pipeline = KnowledgePipeline()
    filters = {"models": [model]} if model else None
    pack = pipeline.search(query, top_k=top_k, filters=filters)
    rprint(json.dumps(pack, ensure_ascii=False, indent=2))


@app.command("reembed")
def reembed_cmd(
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w"),
    batch_size: int = typer.Option(64, "--batch-size"),
) -> None:
    """Re-embed all cached chunks with the active embedding policy (docs/08)."""
    from knowledge.embeddings import active_embed_model, embed_with_meta

    reg = get_registry()
    items = [
        (cid, payload)
        for cid, payload in reg.chunk_payloads.items()
        if not workspace
        or (payload.get("workspace_id") or reg.settings.default_workspace_id) == workspace
    ]
    if not items:
        rprint(json.dumps({"ok": True, "reembedded": 0, "note": "no cached chunks"}))
        return
    model = active_embed_model(reg.settings)
    done = 0
    for start in range(0, len(items), max(1, batch_size)):
        batch = items[start : start + max(1, batch_size)]
        vectors, resolved = embed_with_meta(
            [p.get("text", "") for _, p in batch], settings=reg.settings
        )
        for (cid, payload), vec in zip(batch, vectors):
            payload["embed_model"] = model
            reg.vector.upsert(cid, vec, payload)
        done += len(batch)
        rprint(f"reembedded {done}/{len(items)} (model={resolved.provider})")
    from knowledge.persist import save_registry

    save_registry(reg)
    rprint(
        json.dumps(
            {"ok": True, "reembedded": done, "model": model},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    app()
