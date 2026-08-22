import MarkdownBody from "../MarkdownBody";
import SclDiffPreview, {
  looksLikeSclPreviewMessage,
  previewFocusFromMessage,
  stripSclPreviewFences,
} from "../SclDiffPreview";
import { sclDiffsForFocus } from "../plc/detail";
import type { PlcCitation, PlcJobDetail } from "../api";
import { formatMsgTime } from "./layout";
import { userBubbleParts, type ChatMsg, type ChatScope } from "./model";

export type ChatSendOptions = {
  message: string;
  file?: File | null;
  focusNodeId?: string | null;
  blockName?: string | null;
  displayUser?: string;
  scopeLabel?: string;
};

type ChatMessagesProps = {
  messages: ChatMsg[];
  copiedId: string | null;
  busy: boolean;
  plcJob: PlcJobDetail | null;
  chatScope: ChatScope | null;
  onCopyMessage: (message: ChatMsg) => Promise<void> | void;
  onFocusNode: (ref: string) => void;
  onSendTurn: (options: ChatSendOptions) => Promise<void> | void;
};

function UserBubbleText({ message }: { message: ChatMsg }) {
  const parts = userBubbleParts(message);
  return (
    <>
      {parts.prefix ? <span className="bubble-scope">@{parts.prefix}</span> : null}
      {parts.body}
    </>
  );
}

function EvidenceChips({
  citations,
  onFocusNode,
}: {
  citations?: PlcCitation[];
  onFocusNode?: (ref: string) => void;
}) {
  if (!citations?.length) return null;
  return (
    <div className="evidence-chips" aria-label="图谱证据">
      {citations.slice(0, 6).map((c, i) => {
        const label = [c.block, c.edge_type, c.target ? `→ ${c.target}` : ""]
          .filter(Boolean)
          .join(" ");
        const focusRef = c.nodeId || c.block || "";
        const title = [c.network, c.snippet || c.evidence].filter(Boolean).join(" · ");
        if (focusRef && onFocusNode) {
          return (
            <button
              key={`${c.block}-${c.edge_type}-${c.target}-${i}`}
              type="button"
              className="plc-chip evidence-chip"
              title={title || "定位到画布节点"}
              onClick={() => onFocusNode(focusRef)}
            >
              {label || c.snippet || "证据"}
            </button>
          );
        }
        return (
          <span
            key={`${c.block}-${c.edge_type}-${c.target}-${i}`}
            className="plc-chip"
            title={title}
          >
            {label || c.snippet || "证据"}
          </span>
        );
      })}
    </div>
  );
}

export function ChatMessages({
  messages,
  copiedId,
  busy,
  plcJob,
  chatScope,
  onCopyMessage,
  onFocusNode,
  onSendTurn,
}: ChatMessagesProps) {
  return (
    <>
                {messages.map((m) => (
              <div key={m.id} className={`bubble ${m.role}`}>
                <div className="bubble-meta">
                  <span className="bubble-time">{formatMsgTime(m.at)}</span>
                  <button
                    type="button"
                    className="bubble-copy"
                    onClick={() => void onCopyMessage(m)}
                    title="复制内容"
                  >
                    {copiedId === m.id ? "已复制" : "复制"}
                  </button>
                </div>
                <div className="bubble-body">
                  {m.role === "assistant" ? (
                    <>
                      <MarkdownBody
                        content={
                          looksLikeSclPreviewMessage(m.content)
                            ? stripSclPreviewFences(m.content)
                            : m.content
                        }
                      />
                      {looksLikeSclPreviewMessage(m.content) ? (
                        <SclDiffPreview
                          diffs={sclDiffsForFocus(
                            plcJob,
                            previewFocusFromMessage(m.content) ||
                              (chatScope && chatScope.kind !== "plc_tag"
                                ? chatScope.blockName
                                : null),
                          )}
                        />
                      ) : null}
                      <EvidenceChips citations={m.citations} onFocusNode={onFocusNode} />
                    </>
                  ) : (
                    <UserBubbleText message={m} />
                  )}
                  {m.role === "assistant" && /展开\s*SCL/.test(m.content) ? (
                    <div className="chat-quick">
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => {
                          const hit = m.content.match(/\*\*`([^`]+)`\*\*/);
                          const block = hit?.[1] || chatScope?.blockName || null;
                          void onSendTurn({
                            message: block ? `@${block} 展开 SCL` : "展开 SCL",
                            focusNodeId: chatScope?.nodeId,
                            blockName: block,
                            displayUser: "展开 SCL",
                            scopeLabel: block || undefined,
                          });
                        }}
                      >
                        展开完整 SCL
                      </button>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => {
                          const hit = m.content.match(/\*\*`([^`]+)`\*\*/);
                          const block = hit?.[1] || chatScope?.blockName || null;
                          void onSendTurn({
                            message: block ? `@${block} 优化建议` : "优化建议",
                            focusNodeId: chatScope?.nodeId,
                            blockName: block,
                            displayUser: "优化建议",
                            scopeLabel: block || undefined,
                          });
                        }}
                      >
                        优化建议
                      </button>
                    </div>
                  ) : null}
                </div>
              </div>
            ))}
    </>
  );
}
