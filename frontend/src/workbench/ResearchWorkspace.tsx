import type { Dispatch, SetStateAction } from "react";
import CitationRail from "../CitationRail";
import Timeline from "../Timeline";
import { plcExportUrl, plcZapUrl, type PlcJobDetail, type PlcProjectBrief } from "../api";
import { ProjectBriefCard } from "../plc/ProjectBrief";
import KnowledgeCanvas, {
  type CanvasFocusRequest,
  type KnowledgeCanvasData,
  type KnowledgeNode,
  type WritebackChipHint,
} from "../KnowledgeCanvas";
import { NodeWorkbench, type NodeWorkbenchTab } from "../plc/canvas/NodeWorkbench";
import type { CanvasJumpIntent } from "../plc/canvas/jump";
import { PlcCoverageStrip } from "../plc/CoverageStrip";
import { DeviceSensorInspect, DeviceSensorPanel } from "../plc/DeviceSensorPanel";
import type { PlcCanvasTab } from "../plc/usePlcWorkspace";
import type { CitationItem, ResearchEvent } from "../researchModel";
import type { ChatMsg, ChatScope } from "./model";

type ResearchWorkspaceProps = {
  busy: boolean;
  canvas: KnowledgeCanvasData;
  canvasFocus: CanvasFocusRequest | null;
  canvasTab: PlcCanvasTab;
  citations: CitationItem[];
  chatScope: ChatScope | null;
  events: ResearchEvent[];
  messages: ChatMsg[];
  noteFocusKey: number;
  plcJob: PlcJobDetail | null;
  plcJobId: string | null;
  switchCue: string | null;
  workbenchOpen: boolean;
  workbenchTab: NodeWorkbenchTab;
  projectBrief?: PlcProjectBrief | null;
  onAskInChat: (node: KnowledgeNode) => void;
  onCanvasChange: Dispatch<SetStateAction<KnowledgeCanvasData>>;
  onConfirmWriteback: (blockName?: string | null) => Promise<void> | void;
  onDeepDive: (node: KnowledgeNode, question: string) => Promise<void> | void;
  onFocusNode: (ref: string) => void;
  onMarkNote: (node: KnowledgeNode) => void;
  onSelectNode: (node: KnowledgeNode | null) => void;
  onOptimizePropose: () => Promise<void> | void;
  onRetryStructure?: (names?: string[]) => Promise<void> | void;
  onSclPreview: (blockName: string) => Array<{ block?: string }>;
  onTabChange: (tab: PlcCanvasTab) => void;
  onViewSources: (node: KnowledgeNode) => void;
  onWorkbenchClose: () => void;
  onWorkbenchTabChange: (tab: NodeWorkbenchTab) => void;
  onWritebackHint: (blockName: string) => WritebackChipHint;
  onAskHandover?: (prompt: string) => void;
  onJumpCanvas?: (intent: CanvasJumpIntent) => void;
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
  messages,
  noteFocusKey,
  plcJob,
  plcJobId,
  switchCue,
  workbenchOpen,
  workbenchTab,
  projectBrief,
  onAskInChat,
  onCanvasChange,
  onConfirmWriteback,
  onDeepDive,
  onFocusNode,
  onMarkNote,
  onSelectNode,
  onOptimizePropose,
  onRetryStructure,
  onSclPreview,
  onTabChange,
  onViewSources,
  onWorkbenchClose,
  onWorkbenchTabChange,
  onWritebackHint,
  onAskHandover,
  onJumpCanvas,
}: ResearchWorkspaceProps) {
  const scopedBlockName =
    chatScope && chatScope.kind !== "plc_tag" ? chatScope.blockName : undefined;
  const workbenchNode =
    (chatScope &&
      (canvas.nodes.find((n) => n.id === chatScope.nodeId) || {
        id: chatScope.nodeId,
        label: chatScope.label,
        kind: chatScope.kind,
        x: 0,
        y: 0,
        source: { type: "plc", block_name: chatScope.blockName },
      })) ||
    null;

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
            className={canvasTab === "sensors" ? "on" : ""}
            onClick={() => onTabChange("sensors")}
          >
            传感器
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
          <button
            type="button"
            className={canvasTab === "brief" ? "on" : ""}
            onClick={() => onTabChange("brief")}
          >
            简报
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
        {canvasTab === "sensors" ? (
          <DeviceSensorPanel
            jobId={plcJob?.status === "ready" ? plcJobId : null}
            focusSymbol={
              chatScope?.kind === "plc_tag" && !chatScope.nodeId.startsWith("plc_tt_")
                ? chatScope.label
                : undefined
            }
            onJumpCanvas={onJumpCanvas}
          />
        ) : canvasTab === "canvas" ? (
          <>
            {plcJobId ? (
              <ProjectBriefCard
                brief={projectBrief || null}
                compact
                onAsk={onAskHandover}
                onOpenFull={() => onTabChange("brief")}
                onJumpCanvas={onJumpCanvas}
              />
            ) : null}
            <PlcCoverageStrip
              detail={plcJob}
              busy={busy}
              onRetryStructure={onRetryStructure}
            />
            {plcJobId &&
            plcJob?.status === "ready" &&
            chatScope?.kind === "plc_tag" &&
            !chatScope.nodeId.startsWith("plc_tt_") ? (
              <DeviceSensorInspect
                jobId={plcJobId}
                symbol={chatScope.label}
                onJumpCanvas={onJumpCanvas}
              />
            ) : null}
            <div className={`kg-stage${workbenchOpen ? " with-workbench" : ""}`}>
              <KnowledgeCanvas
                data={canvas}
                logicGraph={logicGraphFromJob(plcJob)}
                knowledgeGraph={plcJob?.knowledge_graph || null}
                plcJob={plcJob}
                onChange={onCanvasChange}
                onSelectNode={onSelectNode}
                onAskInChat={onAskInChat}
                onViewSources={onViewSources}
                onMarkNote={onMarkNote}
                focusRequest={canvasFocus}
                busy={busy}
              />
              {workbenchOpen && workbenchNode ? (
                <NodeWorkbench
                  node={workbenchNode}
                  job={plcJob}
                  messages={messages}
                  busy={busy}
                  tab={workbenchTab}
                  noteFocusKey={noteFocusKey}
                  switchCue={switchCue}
                  inspectCtx={{
                    job: plcJob,
                    knowledgeGraph: plcJob?.knowledge_graph || null,
                  }}
                  writebackHint={onWritebackHint}
                  getSclPreview={onSclPreview}
                  onTabChange={onWorkbenchTabChange}
                  onClose={onWorkbenchClose}
                  onAsk={onDeepDive}
                  onOptimizePropose={onOptimizePropose}
                  onConfirmWriteback={(node) => {
                    const name = String(node.source?.block_name || node.label || "").trim();
                    return onConfirmWriteback(name || undefined);
                  }}
                  onJumpCitation={onFocusNode}
                />
              ) : null}
            </div>
          </>
        ) : canvasTab === "timeline" ? (
          <Timeline events={events} />
        ) : canvasTab === "brief" ? (
          <ProjectBriefCard
            brief={projectBrief || null}
            onAsk={onAskHandover}
            onJumpCanvas={onJumpCanvas}
          />
        ) : (
          <CitationRail citations={citations} />
        )}
      </div>
    </section>
  );
}
