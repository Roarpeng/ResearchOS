import { useEffect, useState } from "react";
import { usePlcWorkspace } from "./plc/usePlcWorkspace";
import type { ChatMsg } from "./workbench/model";
import { ChatPane } from "./workbench/ChatPane";
import { HistoryPane } from "./workbench/HistoryPane";
import { ResearchWorkspace } from "./workbench/ResearchWorkspace";
import { SettingsModal } from "./workbench/SettingsModal";
import { useTriSplit } from "./workbench/useTriSplit";

export default function App() {
  const [showSettings, setShowSettings] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const {
    active,
    activeId,
    busy,
    canvas,
    canvasFocus,
    canvasTab,
    chatEndRef,
    chatScope,
    citations,
    composerRef,
    draft,
    events,
    file,
    fileRef,
    interrupts,
    messages,
    plcJob,
    plcJobId,
    status,
    topics,
    applyChatScope,
    clearAllTopics,
    clearChatScope,
    deleteTopic,
    onCancel,
    onConfirmWriteback,
    onDeepDive,
    onFocusNode,
    onAskInChat,
    onOptimizePropose,
    onScopePrompt,
    onResume,
    onSend,
    openTopic,
    sclPreviewFor,
    scopedPrompts,
    sendTurn,
    setCanvas,
    setCanvasTab,
    setDraft,
    setFile,
    startNew,
    writebackHintFor,
  } = usePlcWorkspace();
  const {
    chatW,
    historyCollapsed,
    historyShownW,
    onTriSplitPointerDown,
    resetTriSplit,
    toggleHistoryCollapsed,
    triRef,
  } = useTriSplit();

  useEffect(() => {
    if (!showSettings) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setShowSettings(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [showSettings]);

  async function copyMessage(m: ChatMsg) {
    try {
      await navigator.clipboard.writeText(m.content);
      setCopiedId(m.id);
      window.setTimeout(() => setCopiedId((id) => (id === m.id ? null : id)), 1200);
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand-mark" aria-label="ResearchOS">
          <span className="logo-mark" aria-hidden>
            <span className="logo-r">R</span>
            <span className="logo-os">OS</span>
          </span>
          <span className="brand-text">ResearchOS</span>
        </div>
        <div className="topbar-right">
          {status ? <span className="status-chip">{status}</span> : null}
          <button type="button" className="ghost" onClick={() => setShowSettings(true)}>
            设置
          </button>
        </div>
      </header>

      <div className="tri" ref={triRef}>
        <HistoryPane
          activeId={activeId}
          collapsed={historyCollapsed}
          topics={topics}
          width={historyShownW}
          onClearAll={clearAllTopics}
          onDeleteTopic={deleteTopic}
          onOpenTopic={openTopic}
          onStartNew={startNew}
          onToggleCollapsed={toggleHistoryCollapsed}
        />

        <div
          className={`pane-split${historyCollapsed ? " disabled" : ""}`}
          role="separator"
          aria-orientation="vertical"
          aria-label="调整历史栏宽度"
          aria-valuenow={historyShownW}
          title={historyCollapsed ? "先展开历史栏" : "拖动调节 · 双击恢复默认 · Alt+[ / Alt+]"}
          onPointerDown={(e) => onTriSplitPointerDown("history", e)}
          onDoubleClick={() => resetTriSplit("history")}
        />

        <ChatPane
          activeTitle={active?.title}
          busy={busy}
          chatEndRef={chatEndRef}
          chatScope={chatScope}
          composerRef={composerRef}
          copiedId={copiedId}
          draft={draft}
          file={file}
          fileRef={fileRef}
          interrupts={interrupts}
          messages={messages}
          plcJob={plcJob}
          width={chatW}
          onCancelTask={() => void onCancel()}
          onClearChatScope={clearChatScope}
          onCopyMessage={copyMessage}
          onDraftChange={setDraft}
          onFocusNode={onFocusNode}
          onFileChange={setFile}
          onResolveInterrupt={(resolution, interruptId) => void onResume(resolution, interruptId)}
          onScopePrompt={onScopePrompt}
          onSend={onSend}
          onSendTurn={sendTurn}
          scopePrompts={scopedPrompts}
        />

        <div
          className="pane-split"
          role="separator"
          aria-orientation="vertical"
          aria-label="调整对话栏宽度"
          aria-valuenow={chatW}
          title="拖动调节 · 双击恢复默认 · [ / ]"
          onPointerDown={(e) => onTriSplitPointerDown("chat", e)}
          onDoubleClick={() => resetTriSplit("chat")}
        />

        <ResearchWorkspace
          busy={busy}
          canvas={canvas}
          canvasFocus={canvasFocus}
          canvasTab={canvasTab}
          citations={citations}
          chatScope={chatScope}
          events={events}
          plcJob={plcJob}
          plcJobId={plcJobId}
          onAskInChat={onAskInChat}
          onCanvasChange={setCanvas}
          onConfirmWriteback={onConfirmWriteback}
          onDeepDive={onDeepDive}
          onSelectNode={applyChatScope}
          onOptimizePropose={onOptimizePropose}
          onSclPreview={sclPreviewFor}
          onTabChange={setCanvasTab}
          onWritebackHint={writebackHintFor}
        />
      </div>

      {showSettings ? <SettingsModal onClose={() => setShowSettings(false)} /> : null}
    </div>
  );
}
