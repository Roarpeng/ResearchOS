"""PLC Intelligence job schemas — ResearchOS industrial feature (not the whole product)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PlcJobCreatePath(BaseModel):
    """Create a PLC ingest job from a server-visible path."""

    source_type: Literal["path"] = "path"
    path: str = Field(..., description="Absolute path under PLC_PATH_ALLOWLIST roots")
    project_name: str = ""
    publish_graph: bool = True
    plc_name: str = ""
    tia_version: str = ""


class PlcChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    block_name: str | None = Field(
        default=None,
        description="Optional PLC block focus (OB/FB/FC/DB name)",
    )


class PlcGraphQueryRequest(BaseModel):
    op: str
    block_name: str | None = None
    tag: str | None = None
    target_block: str | None = None
    roots: list[str] | None = None


class PlcGraphQueryResponse(BaseModel):
    op: str
    result: Any
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class PlcChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    block_name: str | None = None
    created_at: datetime | None = None
    citations: list[dict[str, Any]] = Field(default_factory=list)


class PlcAnalyzeRequest(BaseModel):
    """Optional block focus for deterministic KG/folded-logic analysis."""

    block_name: str | None = Field(
        default=None,
        description="Optional PLC block focus (OB/FB/FC/DB name)",
    )


class PlcLogicNode(BaseModel):
    id: str
    label: str
    type: str
    props: dict[str, Any] = Field(default_factory=dict)


class PlcLogicEdge(BaseModel):
    source: str
    target: str
    type: str


class PlcJobSummary(BaseModel):
    id: str
    status: str
    source_type: str
    source_path: str | None = None
    project_path: str | None = None
    project_name: str = ""
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    error: str | None = None
    export_ready: bool = False
    coverage: dict[str, Any] | None = Field(
        default=None,
        description="Language/Part/TODO histogram; also on GET job detail",
    )


class PlcJobDetail(PlcJobSummary):
    extraction_notes: list[str] = Field(default_factory=list)
    progress: list[dict[str, Any]] = Field(default_factory=list)
    openness_export_dir: str | None = None
    logic_graph: dict[str, Any] = Field(default_factory=dict)
    knowledge_graph: dict[str, Any] = Field(default_factory=dict)
    folded_logic: dict[str, Any] = Field(default_factory=dict)
    scl_sources: dict[str, str] = Field(default_factory=dict)
    report: str = ""
    graph_publish: dict[str, Any] | None = None
    chat: list[PlcChatTurn] = Field(default_factory=list)
    blocks: list[dict[str, Any]] = Field(default_factory=list)
    changeset: dict[str, Any] | None = None
    writeback: dict[str, Any] | None = None
    optimize_plan: str = ""
    scl_files: dict[str, str] = Field(default_factory=dict)
    scl_diffs: list[dict[str, Any]] = Field(default_factory=list)
    scl_skipped: list[dict[str, Any]] = Field(default_factory=list)
    source_xmls: list[str] = Field(default_factory=list)
    timings: dict[str, int] = Field(
        default_factory=dict,
        description="Ingest stage wall-clock timings in milliseconds",
    )
    coverage: dict[str, Any] = Field(default_factory=dict)


class PlcProposeChangeRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    block_name: str | None = None


class PlcOptimizeRequest(BaseModel):
    """Evidence-gated optimization proposal (dead + decouple + SCL rewrite)."""

    block_name: str | None = Field(
        default=None,
        description="Optional focus block; project-wide dead-block scan always runs",
    )
    message: str = Field(
        default="优化工程逻辑并准备反写",
        max_length=4000,
    )


class PlcWritebackRequest(BaseModel):
    """HITL confirm: apply KG changes and optionally import XML/SCL into .apxx."""

    project_path: str | None = Field(
        default=None,
        description="Target .ap19/.apxx; defaults to job.project_path from ingest",
    )
    plc_name: str = ""
    accept_changeset: bool = True
    execute_openness_import: bool = True
    archive_zap: bool = Field(
        default=True,
        description="After successful Openness import+save, Archive compressed .zap*",
    )
    xml_paths: list[str] = Field(
        default_factory=list,
        description="Optional XML files to stage; defaults to job source XML",
    )
