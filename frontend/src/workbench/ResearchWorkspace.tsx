import type { Dispatch, SetStateAction } from "react";
import CitationRail from "../CitationRail";
import Timeline from "../Timeline";
import { plcExportUrl, plcZapUrl, type PlcJobDetail } from "../api";
import KnowledgeCanvas, {
  type CanvasFocusRequest,
  type KnowledgeCanvasData,
  type KnowledgeNode,
  type WritebackChipHint,
} from "../KnowledgeCanvas";
import { PlcCoverageStrip } from "../plc/CoverageStrip";
import type { PlcCanvasTab } from "../plc/usePlcWorkspace";
import type { CitationItem, ResearchEvent } from "../researchModel";
import type { ChatScope } from "./model";

type ResearchWorkspaceProps = {
  busy: boolean;
  canvas: KnowledgeCanvasData;
  canvasFocus: CanvasFocusRequest | null;
  canvasTab: PlcCanvasTab;
  citations: CitationItem[];
  chatScope: ChatScope | null;
  events: ResearchEvent[];
  plcJob: PlcJobDetail | null;
  plcJobId: string | null;
  onAskInChat: (node: KnowledgeNode) => void;
  onCanvasChange: Dispatch<SetStateAction<KnowledgeCanvasData>>;
  onConfirmWriteback: (blockName?: string | null) => Promise<void> | void;
  onDeepDive: (node: KnowledgeNode, question: string) => Promise<void> | void;
  onSelectNode: (node: KnowledgeNode | null) => void;
  onOptimizePropose: () => Promise<void> | void;
  onSclPreview: (blockName: string) => Array<{ block?: string }>;
  onTabChange: (tab: PlcCanvasTab) => void;
  onWritebackHint: (blockName: string) => WritebackChipHint;
};

function logicGraphFromJob(job: PlcJobDetail | null) {
  if (!job?.logic_graph) return null;
  return {
    nodes: (job.logic_graph.nodes || []).map((n) => {
      const props = (n.props || {}) as Record<string, unknown>;
      const id = String(n.id || "");
      const fallback = id.includes("::") ? id.split("::").pop() || id : id;
      return {
        id,
        label: String(n.label || props.name || fallback),
        type: n.type ? String(n.type) : undefined,
        props,
      };
    }),
    edges: (job.logic_graph.edges || []).map((e) => ({
      source: String(e.source || ""),
      target: String(e.target || ""),
      type: e.type ? String(e.type) : undefined,
      seq: typeof e.seq === "number" ? e.seq : undefined,
    })),
  };
}

export function ResearchWorkspace({
  busy,
  canvas,
  canvasFocus,
  canvasTab,
  citations,
  chatScope,
  events,
  plcJob,
  plcJobId,
  onAskInChat,
  onCanvasChange,
  onConfirmWriteback,
  onDeepDive,
  onSelectNode,
  onOptimizePropose,
  onSclPreview,
  onTabChange,
  onWritebackHint,
}: ResearchWorkspaceProps) {
  const scopedBlockName =
    chatScope && chatScope.kind !== "plc_tag" ? chatScope.blockName : undefined;

  return (
    <section className="col canvas" aria-label="研究视图">
      <div className="col-head">
        <div className="canvas-tabs" role="tablist" aria-label="研究视图">
          <button
            type="button"
            className={canvasTab === "canvas" ? "on" : ""}
            onClick={() => onTabChange("canvas")}
          >
            画布
          </button>
          <button
            type="button"
            className={canvasTab === "timeline" ? "on" : ""}
            onClick={() => onTabChange("timeline")}
          >
            时间线
          </button>
          <button
            type="button"
            className={canvasTab === "citations" ? "on" : ""}
            onClick={() => onTabChange("citations")}
          >
            引用{citations.length ? ` ${citations.length}` : ""}
          </button>
        </div>
        <div className="col-head-actions">
          {canvasTab === "canvas" && plcJobId && plcJob?.status === "ready" ? (
            <>
              <button
                type="button"
                className="btn-primary compact"
                disabled={busy}
                title="基于图谱生成安全优化提案"
                onClick={() => void onOptimizePropose()}
              >
                优化提案
              </button>
              <button
                type="button"
                className="ghost compact"
                disabled={busy || !plcJob?.changeset}
                title={
                  scopedBlockName
                    ? `确认 ${chatScope?.label} 的 changeset 并 Openness 反写归档 .zap`
                    : "确认整工程 changeset 并 Openness 反写归档 .zap"
                }
                onClick={() => void onConfirmWriteback(scopedBlockName)}
              >
                确认反写.zap
              </button>
              {(plcJob?.writeback as { zap_path?: string } | null)?.zap_path ? (
                <a href={plcZapUrl(plcJobId)} target="_blank" rel="noreferrer" className="ghost compact">
                  下载.zap
                </a>
              ) : null}
            </>
          ) : null}
          {canvasTab === "canvas" && plcJobId && plcJob?.export_ready ? (
            <a className="ghost compact" href={plcExportUrl(plcJobId)} target="_blank" rel="noreferrer">
              导出
            </a>
          ) : null}
        </div>
      </div>
      <div className="canvas-body canvas-kg">
        {canvasTab === "canvas" ? (
          <>
            <PlcCoverageStrip detail={plcJob} />
            <KnowledgeCanvas
              data={canvas}
              logicGraph={logicGraphFromJob(plcJob)}
              knowledgeGraph={plcJob?.knowledge_graph || null}
              onChange={onCanvasChange}
              onDeepDive={onDeepDive}
              onConfirmWriteback={(node) => {
                const name = String(node.source?.block_name || node.label || "").trim();
                return onConfirmWriteback(name || undefined);
              }}
              writebackHint={onWritebackHint}
              getSclPreview={onSclPreview}
              onSelectNode={onSelectNode}
              onAskInChat={onAskInChat}
              focusRequest={canvasFocus}
              busy={busy}
            />
          </>
        ) : canvasTab === "timeline" ? (
          <Timeline events={events} />
        ) : (
          <CitationRail citations={citations} />
        )}
      </div>
    </section>
  );
}
