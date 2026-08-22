import type { FormEvent, RefObject } from "react";
import InterruptBar from "../InterruptBar";
import type { PlcJobDetail } from "../api";
import { ChatMessages, type ChatSendOptions } from "./ChatMessages";
import { NESTED_CHIPS, ROLE_CHIPS, type ChatMsg, type ChatScope } from "./model";

type ChatPaneProps = {
  activeTitle?: string;
  busy: boolean;
  chatEndRef: RefObject<HTMLDivElement | null>;
  chatScope: ChatScope | null;
  composerRef: RefObject<HTMLTextAreaElement | null>;
  copiedId: string | null;
  draft: string;
  file: File | null;
  fileRef: RefObject<HTMLInputElement | null>;
  interrupts: Parameters<typeof InterruptBar>[0]["interrupts"];
  messages: ChatMsg[];
  plcJob: PlcJobDetail | null;
  width: number;
  onCancelTask: () => void;
  onClearChatScope: () => void;
  onCopyMessage: (message: ChatMsg) => Promise<void> | void;
  onDraftChange: (draft: string) => void;
  onFocusNode: (ref: string) => void;
  onFileChange: (file: File | null) => void;
  onResolveInterrupt: (resolution: string, interruptId?: string) => void;
  onScopePrompt: (prompt: string) => void;
  onSend: (event: FormEvent<HTMLFormElement>) => Promise<void> | void;
  onSendTurn: (options: ChatSendOptions) => Promise<void> | void;
  scopePrompts: (scope: ChatScope) => string[];
};

export function ChatPane({
  activeTitle,
  busy,
  chatEndRef,
  chatScope,
  composerRef,
  copiedId,
  draft,
  file,
  fileRef,
  interrupts,
  messages,
  plcJob,
  width,
  onCancelTask,
  onClearChatScope,
  onCopyMessage,
  onDraftChange,
  onFocusNode,
  onFileChange,
  onResolveInterrupt,
  onScopePrompt,
  onSend,
  onSendTurn,
  scopePrompts,
}: ChatPaneProps) {
  return (
    <main
      className="col chat"
      aria-label="当前对话"
      style={{ flex: `0 0 ${width}px`, width }}
    >
      <div className="col-head">
        <h2>对话</h2>
        {activeTitle ? <span className="muted col-head-title">{activeTitle}</span> : null}
      </div>

      <div className="chat-scroll">
        {!messages.length ? (
          <div className="welcome-logo" aria-label="ResearchOS">
            <div className="welcome-mark">
              <span className="logo-r">R</span>
              <span className="logo-os">OS</span>
            </div>
            <div className="welcome-name">ResearchOS</div>
            <div className="welcome-meaning">Research Operating System</div>
          </div>
        ) : null}
        <ChatMessages
          messages={messages}
          copiedId={copiedId}
          busy={busy}
          plcJob={plcJob}
          chatScope={chatScope}
          onCopyMessage={onCopyMessage}
          onFocusNode={onFocusNode}
          onSendTurn={onSendTurn}
        />

        {interrupts.length > 0 ? (
          <InterruptBar
            interrupts={interrupts}
            busy={busy}
            onResolve={(id, resolution) => onResolveInterrupt(resolution, id)}
            onCancel={onCancelTask}
          />
        ) : null}
        <div ref={chatEndRef} />
      </div>

      {chatScope ? (
        <div className="chat-scope-prompts" aria-label="针对当前节点的建议">
          {scopePrompts(chatScope).map((prompt) => (
            <button
              key={prompt}
              type="button"
              className="ghost compact"
              disabled={busy}
              onClick={() => onScopePrompt(prompt)}
            >
              {prompt}
            </button>
          ))}
          {chatScope.kind !== "plc_tag" ? (
            <>
              {ROLE_CHIPS.map((chip) => (
                <button
                  key={chip}
                  type="button"
                  className="ghost compact role-chip"
                  disabled={busy}
                  title={`确认 ${chatScope.label} 的角色`}
                  onClick={() => onScopePrompt(chip)}
                >
                  {chip}
                </button>
              ))}
              {(chatScope.nestDepth || 0) >= 1
                ? NESTED_CHIPS.map((chip) => (
                    <button
                      key={chip}
                      type="button"
                      className="ghost compact role-chip"
                      disabled={busy}
                      title={`确认 ${chatScope.label} 的嵌套 FB 意图`}
                      onClick={() => onScopePrompt(chip)}
                    >
                      {chip}
                    </button>
                  ))
                : null}
            </>
          ) : null}
        </div>
      ) : null}

      <form className="composer composer-plc" onSubmit={onSend}>
        <div className="composer-main">
          {chatScope ? (
            <div className="scope-chip" aria-label={`正在问 ${chatScope.label}`}>
              <span className="scope-chip-label">正在问 · {chatScope.label}</span>
              <button
                type="button"
                className="scope-chip-clear"
                title="回到整工程对话"
                aria-label="清除节点范围，回到整工程对话"
                onClick={onClearChatScope}
              >
                ×
              </button>
            </div>
          ) : null}
          <textarea
            ref={composerRef}
            value={draft}
            onChange={(e) => onDraftChange(e.target.value)}
            placeholder={
              chatScope ? `问 ${chatScope.label}：谁写这个输出？` : "需要探索什么吗？"
            }
            rows={2}
            disabled={busy}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                e.currentTarget.form?.requestSubmit();
              }
            }}
          />
          <div className="composer-attach">
            <label
              className={`file-chip${file ? " has-file" : ""}`}
              title={
                file
                  ? file.name
                  : "上传西门子 .zap / 整包 zip / SimaticML XML"
              }
            >
              <input
                ref={fileRef}
                type="file"
                accept=".xml,.zip,.zap,.zap15,.zap16,.zap17,.zap18,.zap19,.zap20"
                onChange={(e) => onFileChange(e.target.files?.[0] || null)}
                aria-label={file ? `已选择 ${file.name}` : "上传工程文件"}
              />
              {file ? (
                <span className="file-chip-name">{file.name}</span>
              ) : (
                <span className="file-chip-plus" aria-hidden="true">
                  +
                </span>
              )}
            </label>
          </div>
        </div>
        <button
          type="submit"
          className="btn-primary"
          disabled={busy || (!draft.trim() && !file)}
          aria-busy={busy}
        >
          {busy ? "…" : "发送"}
        </button>
      </form>
    </main>
  );
}
