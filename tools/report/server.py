"""MCP server for report.export."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from tools.report.export import export_report, report_preview, validate_citations

mcp = FastMCP("report")


@mcp.tool(name="report.export")
def report_export(
    markdown: str,
    format: str = "pdf",
    engine: str = "auto",
    title: str = "ResearchOS Report",
    task_id: str | None = None,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Export Markdown report to pdf/docx/markdown."""
    return export_report(
        markdown,
        format=format,  # type: ignore[arg-type]
        engine=engine,  # type: ignore[arg-type]
        title=title,
        task_id=task_id,
        output_dir=output_dir,
    )


@mcp.tool(name="report.preview")
def report_preview_tool(
    markdown: str,
    title: str = "ResearchOS Report",
) -> dict[str, Any]:
    """Side-effect-free short preview with citation stats."""
    return report_preview(markdown, title=title)


@mcp.tool(name="report.validate_citations")
def report_validate_citations(
    markdown: str,
    citations: list[dict[str, Any]] | None = None,
    on_policy: str = "strict",
) -> dict[str, Any]:
    """Pre-export completeness check for in-text citation markers."""
    return validate_citations(
        markdown,
        citations or [],
        on_policy=on_policy,  # type: ignore[arg-type]
    )


@mcp.tool(name="report.list_templates")
def report_list_templates() -> dict[str, Any]:
    return {
        "templates": [
            {"id": "industrial_research_v1", "title": "Industrial research"},
            {"id": "competitor_analysis_v1", "title": "Competitor analysis"},
            {"id": "meeting_decision_v1", "title": "Decision memo"},
        ]
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
