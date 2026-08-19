import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
import {
  cancelTask,
  connectResearchStream,
  deleteResearchTask,
  fetchPlcJob,
  fetchTask,
  listResearchTasks,
  plcExportUrl,
  plcZapUrl,
  optimizePlcJob,
  writebackPlcJob,
  postChatTurn,
  resumeTask,
  unwrapTask,
  waitForPlcJob,
  type PlcCitation,
  type PlcCoverage,
  type PlcJobDetail,
} from "./api";
import KnowledgeCanvas, {
  autoLayoutKnowledge,
  type CanvasFocusRequest,
  type KnowledgeCanvasData,
  type KnowledgeNode,
} from "./KnowledgeCanvas";
import MarkdownBody from "./MarkdownBody";
import SettingsPanel from "./SettingsPanel";

type Topic = {
  id: string;
  title: string;
  status: string;
  route?: string;
  plcJobId?: string | null;
};

type ChatScope = {
  nodeId: string;
  blockName: string;
  label: string;
  kind: string;
  looksLikeOutput?: boolean;
  nestDepth?: number;
};

const ROLE_CHIPS = ["工艺主控", "设备驱动", "厂商库", "可拆辅助", "不要动"] as const;
const NESTED_CHIPS = ["必须的多实例", "意外耦合"] as const;

type ChatMsg = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  at: number;
  citations?: PlcCitation[];
  /** Node-scoped user turns render a small `@FB_Motor` prefix. */
  scopeLabel?: string;
};

const PLC_SCOPE_KINDS = new Set([
  "plc_block",
  "plc_ob",
  "plc_db",
  "plc_udt",
  "plc_instance",
  "plc_tag",
]);

const TRI_SIZES_KEY = "researchos.tri.sizes";
const TRI_DEFAULT = { history: 220, chat: 400 };
const HISTORY_MIN = 160;
const HISTORY_MAX = 400;
const HISTORY_COLLAPSED_W = 48;
const CHAT_MIN = 280;
const CHAT_MAX = 720;
const CANVAS_MIN = 260;
const PANE_STEP = 24;

function clamp(n: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, n));
}

function coverageConvertedPct(cov: PlcCoverage | null | undefined): number {
  const total = Number(cov?.total_blocks || 0);
  const converted = Number(cov?.converted || 0);
  if (!total) return 0;
  return Math.max(0, Math.min(100, Math.round((converted / total) * 100)));
}

function topTodoParts(cov: PlcCoverage | null | undefined, limit = 4): Array<{ name: string; count: number }> {
  const top = cov?.top_untranslated_parts || [];
  if (top.length) {
    return top
      .map((r) => ({ name: String(r.name || ""), count: Number(r.count || 0) }))
      .filter((r) => r.name)
      .slice(0, limit);
  }
  return Object.entries(cov?.todo_histogram || {})
    .map(([name, count]) => ({ name, count: Number(count) }))
    .sort((a, b) => b.count - a.count)
    .slice(0, limit);
}

function obCallTree(detail: PlcJobDetail | null): string[] {
  const nodes = detail?.logic_graph?.nodes || [];
  const edges = (detail?.logic_graph?.edges || []).filter((e) => String(e.type || "") === "CALLS");
  if (!edges.length) return [];
  const labelOf = (id: string) => {
    const n = nodes.find((x) => String(x.id || "") === id);
    const props = (n?.props || {}) as Record<string, unknown>;
    const raw = String(n?.label || props.name || id);
    return raw.includes("::") ? raw.split("::").pop() || raw : raw;
  };
  const obs = nodes.filter((n) => {
    const props = (n.props || {}) as Record<string, unknown>;
    const t = String(n.type || props.block_type || "").toUpperCase();
    const name = String(props.name || n.label || "");
    return t === "OB" || /^ob\d+/i.test(name) || name === "Main";
  });
  const roots = obs.length ? obs : nodes.slice(0, 1);
  const lines: string[] = [];
  for (const ob of roots.slice(0, 2)) {
    const oid = String(ob.id || "");
    const kids = edges
      .filter((e) => String(e.source || "") === oid)
      .map((e) => labelOf(String(e.target || "")))
      .filter(Boolean);
    if (!kids.length) continue;
    lines.push(`${labelOf(oid)} → ${kids.slice(0, 8).join(" → ")}`);
  }
  return lines.slice(0, 3);
}

function PlcCoverageStrip({ detail }: { detail: PlcJobDetail | null }) {
  const cov = detail?.coverage;
  if (!cov || !Number(cov.total_blocks || 0)) return null;
  const pct = coverageConvertedPct(cov);
  const r = 16;
  const c = 2 * Math.PI * r;
  const dash = (pct / 100) * c;
  const todos = topTodoParts(cov);
  const tree = obCallTree(detail);
  const rate = Number(cov.todo_rate || 0);
  const skipChips: string[] = [];
  const seenSkip = new Set<string>();
  for (const [cat, row] of Object.entries(cov.categories || {})) {
    for (const skip of row.skipped_reasons || []) {
      const reason = String(skip.reason || "").trim();
      if (!reason) continue;
      const key = `${cat}:${reason}`;
      if (seenSkip.has(key)) continue;
      seenSkip.add(key);
      skipChips.push(`${cat}/${reason}`);
      if (skipChips.length >= 8) break;
    }
    if (skipChips.length >= 8) break;
  }
  return (
    <div className="plc-coverage" aria-label="转换覆盖率">
      <svg className="plc-coverage-ring" viewBox="0 0 40 40" width="40" height="40" aria-hidden="true">
        <circle cx="20" cy="20" r={r} fill="none" stroke="var(--line)" strokeWidth="4" />
        <circle
          cx="20"
          cy="20"
          r={r}
          fill="none"
          stroke="var(--accent)"
          strokeWidth="4"
          strokeDasharray={`${dash} ${c - dash}`}
          strokeLinecap="round"
          transform="rotate(-90 20 20)"
        />
        <text x="20" y="22" textAnchor="middle" fontSize="9" fill="currentColor">
          {pct}%
        </text>
      </svg>
      <div className="plc-coverage-meta">
        <div>
          已转换 {cov.converted ?? 0}/{cov.total_blocks ?? 0} · TODO {rate.toLocaleString(undefined, { style: "percent", maximumFractionDigits: 1 })}
          {cov.safety_block_count ? ` · F-block ${cov.safety_block_count}` : ""}
        </div>
        {todos.length ? (
          <div className="plc-coverage-todos">
            未译 Part：
            {todos.map((t) => (
              <span key={t.name} className="plc-chip">
                {t.name} × {t.count}
              </span>
            ))}
          </div>
        ) : (
          <div className="muted">无未译 Part</div>
        )}
        {tree.length ? <div className="plc-coverage-tree">OB 调用：{tree.join("；")}</div> : null}
        {skipChips.length ? (
          <div className="plc-coverage-todos">
            Openness 跳过：
            {skipChips.map((s) => (
              <span key={s} className="plc-chip">
                {s}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function looksLikeOutputCoil(node: KnowledgeNode): boolean {
  const label = String(node.label || "");
  const summary = String(node.summary || "");
  const quote = String(node.source?.quote || "");
  const blob = `${label} ${summary} ${quote}`;
  if (/WRITE/i.test(summary)) return true;
  if (/^(Q|%Q|Y)\b/i.test(label)) return true;
  return /%Q|线圈|coil|output|输出/i.test(blob);
}

function isPlcScopeNode(node: KnowledgeNode | null | undefined): boolean {
  if (!node) return false;
  if (PLC_SCOPE_KINDS.has(String(node.kind || ""))) return true;
  return Boolean(node.source?.type === "plc" && (node.source.block_name || node.source.quote));
}

function chatScopeFromNode(node: KnowledgeNode): ChatScope {
  const blockName =
    String(node.source?.block_name || "").trim() ||
    (node.kind === "plc_tag" ? String(node.label || "").trim() : "") ||
    String(node.label || "").trim();
  return {
    nodeId: node.id,
    blockName,
    label: String(node.label || blockName || node.id),
    kind: String(node.kind || ""),
    looksLikeOutput: looksLikeOutputCoil(node),
    nestDepth: Number(node.source?.nest_depth || 0) || 0,
  };
}

function mentionFromText(text: string): string | null {
  const hit = text.match(/^@(\S+)/);
  return hit?.[1] || null;
}

function userBubbleParts(m: ChatMsg): { prefix?: string; body: string } {
  if (m.scopeLabel) {
    const re = new RegExp(`^@${escapeRegExp(m.scopeLabel)}\\s*`);
    return { prefix: m.scopeLabel, body: m.content.replace(re, "") || m.content };
  }
  const hit = m.content.match(/^@(\S+)\s+([\s\S]+)$/);
  if (hit) return { prefix: hit[1], body: hit[2] };
  return { body: m.content };
}

function attachCitationNodes(citations: PlcCitation[] | undefined, nodes: KnowledgeNode[]): PlcCitation[] {
  if (!citations?.length) return [];
  return citations.map((c) => {
    if (c.nodeId) return c;
    const block = String(c.block || "").trim();
    const target = String(c.target || "").trim();
    const hit =
      nodes.find((n) => n.id === block || n.source?.block_name === block || n.label === block) ||
      nodes.find((n) => n.id === target || n.source?.block_name === target || n.label === target);
    return hit ? { ...c, nodeId: hit.id } : c;
  });
}

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

function loadTriSizes(): { history: number; chat: number; historyCollapsed: boolean } {
  try {
    const raw = localStorage.getItem(TRI_SIZES_KEY);
    if (!raw) return { ...TRI_DEFAULT, historyCollapsed: false };
    const p = JSON.parse(raw) as {
      history?: unknown;
      chat?: unknown;
      historyCollapsed?: unknown;
    };
    return {
      history: clamp(Number(p.history) || TRI_DEFAULT.history, HISTORY_MIN, HISTORY_MAX),
      chat: clamp(Number(p.chat) || TRI_DEFAULT.chat, CHAT_MIN, CHAT_MAX),
      historyCollapsed: Boolean(p.historyCollapsed),
    };
  } catch {
    return { ...TRI_DEFAULT, historyCollapsed: false };
  }
}

function statusTone(status: string): string {
  const s = status.toLowerCase();
  if (/(ready|done|completed|success)/.test(s)) return "ok";
  if (/(error|fail|cancelled|canceled)/.test(s)) return "bad";
  if (/(run|busy|pending|wait|progress|interrupt)/.test(s)) return "busy";
  return "idle";
}

function formatMsgTime(at: number): string {
  try {
    return new Date(at).toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    return "";
  }
}

function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  const tag = el.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  return el.isContentEditable;
}

const emptyCanvas = (): KnowledgeCanvasData => ({ nodes: [], edges: [] });

function pretty(value: unknown): string {
  if (value == null || value === "") return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function titleFromQuery(q: string): string {
  const t = q.trim().replace(/\s+/g, " ");
  return t.length > 42 ? `${t.slice(0, 40)}…` : t || "未命名话题";
}

function formatPlcProgress(detail: PlcJobDetail): string {
  const steps = detail.progress || [];
  const running = [...steps].reverse().find((s) => s.status === "running");
  const last = running || steps[steps.length - 1];
  if (!last?.title) return `PLC ${detail.status || "…"}`;
  const dur =
    typeof last.duration_ms === "number" && last.status !== "running"
      ? ` · ${last.duration_ms}ms`
      : "";
  return `${detail.status}: ${last.title}${dur}`;
}

function normalizeCanvas(raw: unknown): KnowledgeCanvasData {
  const c = (raw || {}) as { nodes?: unknown[]; edges?: unknown[] };
  const nodes = (c.nodes || []).map((n) => {
    const row = n as Record<string, unknown>;
    return {
      id: String(row.id),
      label: String(row.label || row.id),
      summary: row.summary ? String(row.summary) : "",
      kind: row.kind ? String(row.kind) : "insight",
      x: Number(row.x ?? 80),
      y: Number(row.y ?? 80),
      source: (row.source || {}) as KnowledgeNode["source"],
    };
  });
  const edges = (c.edges || []).map((e) => {
    const row = e as Record<string, unknown>;
    return {
      id: String(row.id || `${row.source}-${row.target}`),
      source: String(row.source),
      target: String(row.target),
      label: row.label ? String(row.label) : "",
      user_created: Boolean(row.user_created),
    };
  });
  return { nodes, edges };
}

export default function App() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [plcJobId, setPlcJobId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [draft, setDraft] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [interrupts, setInterrupts] = useState<Record<string, unknown>[]>([]);
  const [plcJob, setPlcJob] = useState<PlcJobDetail | null>(null);
  const [canvas, setCanvas] = useState<KnowledgeCanvasData>(emptyCanvas);
  const [showSettings, setShowSettings] = useState(false);
  const initialTri = loadTriSizes();
  const [historyW, setHistoryW] = useState(initialTri.history);
  const [chatW, setChatW] = useState(initialTri.chat);
  const [historyCollapsed, setHistoryCollapsed] = useState(initialTri.historyCollapsed);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [chatScope, setChatScope] = useState<ChatScope | null>(null);
  const [canvasFocus, setCanvasFocus] = useState<CanvasFocusRequest | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);
  const triRef = useRef<HTMLDivElement | null>(null);
  const historyWRef = useRef(historyW);
  const chatWRef = useRef(chatW);

  const active = topics.find((t) => t.id === activeId) || null;
  const historyShownW = historyCollapsed ? HISTORY_COLLAPSED_W : historyW;

  useEffect(() => {
    historyWRef.current = historyW;
  }, [historyW]);
  useEffect(() => {
    chatWRef.current = chatW;
  }, [chatW]);

  useEffect(() => {
    localStorage.setItem(
      TRI_SIZES_KEY,
      JSON.stringify({ history: historyW, chat: chatW, historyCollapsed }),
    );
  }, [historyW, chatW, historyCollapsed]);

  useEffect(() => {
    if (!showSettings) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setShowSettings(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [showSettings]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTypingTarget(e.target) || e.metaKey || e.ctrlKey) return;
      if (e.key !== "[" && e.key !== "]") return;
      e.preventDefault();
      const grow = e.key === "]";
      const delta = grow ? PANE_STEP : -PANE_STEP;
      const hostW = triRef.current?.getBoundingClientRect().width ?? 1200;
      if (e.altKey) {
        if (historyCollapsed) {
          if (grow) setHistoryCollapsed(false);
          return;
        }
        setHistoryW((w) => {
          const maxHistory = Math.max(
            HISTORY_MIN,
            hostW - chatWRef.current - CANVAS_MIN - 14,
          );
          return clamp(w + delta, HISTORY_MIN, Math.min(HISTORY_MAX, maxHistory));
        });
        return;
      }
      setChatW((w) => {
        const hist = historyCollapsed ? HISTORY_COLLAPSED_W : historyWRef.current;
        const maxChat = Math.max(CHAT_MIN, hostW - hist - CANVAS_MIN - 14);
        return clamp(w + delta, CHAT_MIN, Math.min(CHAT_MAX, maxChat));
      });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [historyCollapsed]);

  function onTriSplitPointerDown(which: "history" | "chat", e: ReactPointerEvent<HTMLDivElement>) {
    if (which === "history" && historyCollapsed) return;
    e.preventDefault();
    const host = triRef.current;
    if (!host) return;
    const el = e.currentTarget;
    el.setPointerCapture(e.pointerId);
    document.body.classList.add("col-resizing");
    const startX = e.clientX;
    const startHistory = historyW;
    const startChat = chatW;
    const hostW = host.getBoundingClientRect().width;
    const histNow = historyCollapsed ? HISTORY_COLLAPSED_W : startHistory;

    const move = (ev: PointerEvent) => {
      const dx = ev.clientX - startX;
      if (which === "history") {
        const next = clamp(startHistory + dx, HISTORY_MIN, HISTORY_MAX);
        const maxHistory = Math.max(HISTORY_MIN, hostW - startChat - CANVAS_MIN - 14);
        setHistoryW(Math.min(next, maxHistory));
      } else {
        const next = clamp(startChat + dx, CHAT_MIN, CHAT_MAX);
        const maxChat = Math.max(CHAT_MIN, hostW - histNow - CANVAS_MIN - 14);
        setChatW(Math.min(next, maxChat));
      }
    };
    const up = (ev: PointerEvent) => {
      el.releasePointerCapture(ev.pointerId);
      document.body.classList.remove("col-resizing");
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  function resetTriSplit(which: "history" | "chat") {
    if (which === "history") {
      setHistoryCollapsed(false);
      setHistoryW(TRI_DEFAULT.history);
    } else setChatW(TRI_DEFAULT.chat);
  }

  function toggleHistoryCollapsed() {
    setHistoryCollapsed((c) => !c);
  }

  async function copyMessage(m: ChatMsg) {
    try {
      await navigator.clipboard.writeText(m.content);
      setCopiedId(m.id);
      window.setTimeout(() => setCopiedId((id) => (id === m.id ? null : id)), 1200);
    } catch {
      /* ignore */
    }
  }

  const refreshTopics = useCallback(async () => {
    try {
      const tasks = await listResearchTasks().catch(() => []);
      setTopics(
        (tasks || [])
          .map((t) => {
            const row = t as {
              id?: string;
              query?: string;
              status?: string;
              route?: string;
              plc_job_id?: string;
              result?: { plc_job_id?: string };
            };
            return {
              id: String(row.id || ""),
              title: titleFromQuery(String(row.query || row.id || "")),
              status: String(row.status || "unknown"),
              route: row.route,
              plcJobId: row.plc_job_id || row.result?.plc_job_id || null,
            };
          })
          .filter((t) => t.id),
      );
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    void refreshTopics();
    return () => wsRef.current?.close();
  }, [refreshTopics]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function pushMsg(
    role: ChatMsg["role"],
    content: string,
    extra?: { citations?: PlcCitation[]; scopeLabel?: string },
  ) {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const at = Date.now();
    setMessages((prev) => [
      ...prev,
      { id, role, content, at, citations: extra?.citations, scopeLabel: extra?.scopeLabel },
    ]);
    return id;
  }

  function focusComposer() {
    window.requestAnimationFrame(() => {
      const el = composerRef.current;
      if (!el) return;
      el.focus();
      el.scrollIntoView({ block: "nearest" });
    });
  }

  function applyChatScope(node: KnowledgeNode | null) {
    if (!node || !isPlcScopeNode(node)) {
      setChatScope(null);
      return;
    }
    setChatScope(chatScopeFromNode(node));
  }

  function clearChatScope() {
    setChatScope(null);
    setCanvasFocus({ key: Date.now(), clear: true });
  }

  function onAskInChat(node: KnowledgeNode) {
    applyChatScope(node);
    focusComposer();
  }

  function onFocusNode(ref: string) {
    const token = String(ref || "").trim();
    if (!token) return;
    const node =
      canvas.nodes.find((n) => n.id === token) ||
      canvas.nodes.find((n) => n.source?.block_name === token || n.label === token);
    if (node) applyChatScope(node);
    setCanvasFocus({
      key: Date.now(),
      nodeId: node?.id || (token.startsWith("plc_") || token.startsWith("sig_") ? token : undefined),
      blockName: node?.source?.block_name || node?.label || token,
    });
  }

  function scopedNode(): KnowledgeNode | null {
    if (!chatScope) return null;
    return (
      canvas.nodes.find((n) => n.id === chatScope.nodeId) || {
        id: chatScope.nodeId,
        label: chatScope.label,
        kind: chatScope.kind,
        x: 0,
        y: 0,
        source: { type: "plc", block_name: chatScope.blockName },
      }
    );
  }

  function scopedPrompts(scope: ChatScope): string[] {
    const tag = scope.kind === "plc_tag";
    const prompts = tag
      ? ["这个信号干什么", "谁读写它", "谁读写这些信号"]
      : ["这个块干什么", "展开 SCL", "分析逻辑", "嵌套链", "理解逻辑", "优化逻辑", "优化SCL", "谁调用它 / 它调用谁", "谁读写这些信号", "优化建议"];
    if (scope.looksLikeOutput) prompts.push("有没有互锁");
    return prompts;
  }

  function startNew() {
    wsRef.current?.close();
    setActiveId(null);
    setMessages([]);
    setDraft("");
    setFile(null);
    setStatus("");
    setInterrupts([]);
    setPlcJob(null);
    setPlcJobId(null);
    setChatScope(null);
    setCanvasFocus(null);
    setCanvas(emptyCanvas());
    if (fileRef.current) fileRef.current.value = "";
  }

  async function deleteTopic(topic: Topic, e: React.MouseEvent) {
    e.stopPropagation();
    e.preventDefault();
    if (!window.confirm(`删除历史对话「${topic.title}」？`)) return;
    try {
      await deleteResearchTask(topic.id);
      setTopics((prev) => prev.filter((t) => t.id !== topic.id));
      if (activeId === topic.id) startNew();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    }
  }

  async function clearAllTopics() {
    if (!topics.length) return;
    if (!window.confirm(`清空全部 ${topics.length} 条历史对话？`)) return;
    const ids = topics.map((t) => t.id);
    await Promise.allSettled(ids.map((id) => deleteResearchTask(id)));
    setTopics([]);
    startNew();
  }

  function canvasGalaxyScore(c: KnowledgeCanvasData | null | undefined): number {
    if (!c?.edges?.length) return 0;
    const want = new Set(["CALLS", "USES", "INSTANCE_OF", "TYPED_AS", "DEPENDS_ON"]);
    return c.edges.filter((e) => want.has(String(e.label || "")) || e.user_created).length;
  }

  function applyCanvasFromTask(task: ReturnType<typeof unwrapTask>, fallback?: unknown) {
    const result = (task.result || {}) as Record<string, unknown>;
    const raw = result.knowledge_canvas ?? fallback;
    if (raw) {
      const next = normalizeCanvas(raw);
      if (next.nodes.length || next.edges.length) {
        const laid = {
          ...next,
          nodes: autoLayoutKnowledge(next.nodes, next.edges),
          edges: next.edges,
        };
        setCanvas((prev) => {
          // Don't let a sparse chat canvas wipe a richer PLC galaxy (causes edge flash on click)
          if (
            canvasGalaxyScore(prev) > canvasGalaxyScore(laid) &&
            prev.nodes.length >= Math.max(1, laid.nodes.length - 2)
          ) {
            return prev;
          }
          return laid;
        });
        return laid;
      }
    }
    return null;
  }

  function applyCanvasFromPlcJob(detail: PlcJobDetail) {
    const blocks = detail.blocks || [];
    if (!blocks.length && !(detail.logic_graph?.nodes || []).length) return;
    const projectId = `plc_proj_${detail.id}`;
    const nodes: KnowledgeNode[] = [
      {
        id: projectId,
        label: String(detail.project_name || detail.id).slice(0, 28),
        summary: `PLC · ${blocks.length} blocks`,
        kind: "plc_project",
        x: 40,
        y: 40,
        source: { type: "plc", plc_job_id: detail.id, project: detail.project_name },
      },
    ];
    blocks.slice(0, 120).forEach((b) => {
      const btype = String(b.type || "Block").toUpperCase();
      const inst = String(b.instance_of || "").trim();
      const nestDepth = Number(b.nest_depth || 0);
      const kind =
        btype === "OB"
          ? "plc_ob"
          : btype === "UDT"
            ? "plc_udt"
            : btype === "DB" && inst
              ? "plc_instance"
              : btype === "DB"
                ? "plc_db"
                : "plc_block";
      const bits = [btype];
      if (b.language) bits.push(String(b.language));
      if (b.networks != null) bits.push(`${b.networks} 网络`);
      if (inst) bits.push(`实例←${inst}`);
      if (nestDepth > 0) bits.push(`嵌套深度 ${nestDepth}`);
      if (b.interface_only || (b.protected && !b.body_available)) {
        bits.push("接口开放·程序体不可用");
      } else if (b.protected) {
        bits.push("Know-how 保护");
      }
      nodes.push({
        id: `plc_b_${detail.id}_${b.name}`,
        label: b.name,
        summary: b.comment || bits.join(" · "),
        kind,
        x: 0,
        y: 0,
        source: {
          type: "plc",
          plc_job_id: detail.id,
          block_name: b.name,
          block_type: b.type,
          instance_of: inst || undefined,
          nest_depth: nestDepth > 0 ? nestDepth : undefined,
          entity_kind: inst ? "instance" : "block",
          project: detail.project_name,
        },
      });
    });
    const known = new Set(nodes.map((n) => n.label));
    for (const n of detail.knowledge_graph?.nodes || []) {
      if (String(n.type || "") !== "Block") continue;
      const props = (n.props || {}) as Record<string, unknown>;
      const name = String(props.name || String(n.id || "").split("::").pop() || "");
      if (!name || known.has(name)) continue;
      known.add(name);
      const btype = String(props.block_type || "DB").toUpperCase();
      const external = Boolean(props.external);
      const nestDepth = Number(props.nest_depth || 0);
      nodes.push({
        id: `plc_b_${detail.id}_${name}`,
        label: name,
        summary: external
          ? `${btype} · 多实例/外部引用（图谱）`
          : Boolean(props.interface_only)
            ? `${btype} · 接口开放·程序体不可用`
            : `${btype} · 由依赖引用补全`,
        kind: external
          ? "plc_instance"
          : btype === "OB"
            ? "plc_ob"
            : btype === "UDT"
              ? "plc_udt"
              : btype === "DB"
                ? "plc_db"
                : "plc_block",
        x: 0,
        y: 0,
        source: {
          type: "plc",
          plc_job_id: detail.id,
          block_name: name,
          block_type: btype,
          entity_kind: external ? "instance" : "block",
          instance_of: external
            ? String(props.instance_of || props.InstanceOfName || "").trim() || undefined
            : undefined,
          nest_depth: nestDepth > 0 ? nestDepth : undefined,
          project: detail.project_name,
        },
      });
    }
    // Tag tables as entry points (individual tags appear when a block is selected)
    const tagTables = (detail.knowledge_graph?.nodes || []).filter(
      (n) => String(n.type || "") === "TagTable",
    );
    const tagCountByTable = new Map<string, number>();
    for (const e of detail.knowledge_graph?.edges || []) {
      if (String(e.type || "") !== "CONTAINS") continue;
      const src = String(e.source || "");
      const tgt = String(e.target || "");
      if (!src.startsWith("TagTable::") || !tgt.startsWith("Tag::")) continue;
      const tname = src.slice("TagTable::".length);
      tagCountByTable.set(tname, (tagCountByTable.get(tname) || 0) + 1);
    }
    tagTables.slice(0, 16).forEach((n, i) => {
      const props = (n.props || {}) as Record<string, unknown>;
      const name = String(props.name || String(n.id || "").split("::").pop() || `Tags${i}`);
      if (known.has(name)) return;
      known.add(name);
      const count = tagCountByTable.get(name) || 0;
      nodes.push({
        id: `plc_tt_${detail.id}_${name}`,
        label: name,
        summary: count ? `标签表 · ${count} 个 Tag（点程序块查看 IO 子图）` : "标签表",
        kind: "plc_tag",
        x: 0,
        y: 0,
        source: {
          type: "plc",
          quote: name,
          plc_job_id: detail.id,
          project: detail.project_name,
        },
      });
    });
    const byLabel = new Map<string, string>();
    nodes.forEach((n) => {
      byLabel.set(n.label, n.id);
      byLabel.set(`Block::${n.label}`, n.id);
      if (n.kind === "plc_tag") byLabel.set(`TagTable::${n.label}`, n.id);
    });
    // Knowledge galaxy: CALLS / USES / INSTANCE_OF / TYPED_AS / DEPENDS_ON (full KG)
    const kgEdges = (detail.knowledge_graph?.edges || []) as Array<{
      source?: string;
      target?: string;
      type?: string;
      weight?: number;
    }>;
    const lgFallback = (detail.logic_graph?.edges || []) as Array<{
      source?: string;
      target?: string;
      type?: string;
      weight?: number;
    }>;
    const rawEdges = (kgEdges.length ? kgEdges : lgFallback)
      .filter((e) => {
        const t = String(e.type || "");
        return (
          t === "CALLS" ||
          t === "USES" ||
          t === "INSTANCE_OF" ||
          t === "TYPED_AS" ||
          t === "DEPENDS_ON"
        );
      })
      .slice()
      .sort((a, b) => {
        const rank: Record<string, number> = {
          CALLS: 0,
          USES: 1,
          INSTANCE_OF: 2,
          TYPED_AS: 3,
          DEPENDS_ON: 4,
        };
        return (
          (rank[String(a.type)] ?? 9) - (rank[String(b.type)] ?? 9) ||
          Number(b.weight || 1) - Number(a.weight || 1)
        );
      });
    const edges: KnowledgeCanvasData["edges"] = [];
    const seen = new Set<string>();
    for (const e of rawEdges) {
      if (edges.length >= 180) break;
      const src = String(e.source || "");
      const tgt = String(e.target || "");
      const et = String(e.type || "DEPENDS_ON");
      const sid =
        byLabel.get(src) || byLabel.get(src.includes("::") ? src.split("::").pop() || "" : src);
      const tid =
        byLabel.get(tgt) || byLabel.get(tgt.includes("::") ? tgt.split("::").pop() || "" : tgt);
      if (!sid || !tid || sid === tid || seen.has(`${sid}|${tid}|${et}`)) continue;
      seen.add(`${sid}|${tid}|${et}`);
      edges.push({
        id: `dep_${edges.length}_${sid}`,
        source: sid,
        target: tid,
        label: et,
        user_created: false,
      });
    }
    setCanvas({
      nodes: autoLayoutKnowledge(nodes, edges),
      edges,
    });
  }

  async function hydratePlc(jobId: string) {
    const detail = await fetchPlcJob(jobId);
    setPlcJob(detail);
    setPlcJobId(jobId);
    return detail;
  }

  async function openTopic(topic: Topic) {
    wsRef.current?.close();
    setActiveId(topic.id);
    setBusy(true);
    setStatus("…");
    setCanvas(emptyCanvas());
    setPlcJob(null);
    setPlcJobId(null);
    setChatScope(null);
    setCanvasFocus(null);
    try {
      const body = await fetchTask(topic.id);
      const task = unwrapTask(body);
      const result = (task.result || {}) as Record<string, unknown>;
      const linked =
        task.plc_job_id ||
        (typeof result.plc_job_id === "string" ? result.plc_job_id : null);
      setStatus(String(task.status || ""));
      setInterrupts((task.interrupts as Record<string, unknown>[]) || []);
      setPlcJobId(linked || null);
      applyCanvasFromTask(task);
      const assistant =
        String(result.assistant_message || "") ||
        pretty(task.result) ||
        String(task.status || "");
      setMessages([
        { id: "q", role: "user", content: topic.title, at: Date.now() },
        { id: "a", role: "assistant", content: assistant, at: Date.now() },
      ]);
      if (linked) {
        let detail = await hydratePlc(linked);
        if (detail.status !== "ready" && detail.status !== "failed") {
          setStatus(formatPlcProgress(detail));
          detail = await waitForPlcJob(linked, {
            intervalMs: 1500,
            onProgress: (d) => {
              setPlcJob(d);
              setStatus(formatPlcProgress(d));
            },
          });
          setPlcJob(detail);
        }
        if (detail.chat?.length) {
          const base = Date.now();
          setMessages(
            detail.chat.map((c, i) => ({
              id: `c${i}`,
              role: c.role === "user" ? "user" : "assistant",
              content: c.content,
              at: base + i,
              citations: c.citations,
              scopeLabel: c.block_name || mentionFromText(c.content) || undefined,
            })),
          );
        }
        // Always rebuild star from job so legacy grid canvases get fixed.
        if (detail.status === "ready") {
          applyCanvasFromPlcJob(detail);
          setStatus("ready");
        } else if (detail.status === "failed") {
          setStatus("failed");
        }
      } else if (task.route !== "plc") {
        connectWs(topic.id);
      }
    } catch (err) {
      setMessages([
        {
          id: "err",
          role: "system",
          content: err instanceof Error ? err.message : String(err),
          at: Date.now(),
        },
      ]);
      setStatus("error");
    } finally {
      setBusy(false);
    }
  }

  function connectWs(id: string) {
    wsRef.current?.close();
    wsRef.current = connectResearchStream(id, (event) => {
      const etype = String(event.event_type || event.type || "");
      const payload = (event.payload || {}) as Record<string, unknown>;
      if (etype === "task.status") setStatus(String(payload.status || ""));
      if (etype === "message.delta" && payload.text) {
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant" && last.id.startsWith("stream-")) {
            return [
              ...prev.slice(0, -1),
              { ...last, content: last.content + String(payload.text) },
            ];
          }
          return [
            ...prev,
            {
              id: `stream-${Date.now()}`,
              role: "assistant",
              content: String(payload.text),
              at: Date.now(),
            },
          ];
        });
      }
    });
  }

  async function sendTurn(opts: {
    message: string;
    file?: File | null;
    focusNodeId?: string | null;
    blockName?: string | null;
    displayUser?: string;
    scopeLabel?: string;
  }) {
    setBusy(true);
    const display = opts.displayUser || opts.message;
    if (display) {
      pushMsg("user", display, {
        scopeLabel: opts.scopeLabel || mentionFromText(display) || undefined,
      });
    }
    const parsing =
      Boolean(opts.file) ||
      /\.(zap\d*|ap\d+|xml|zip)\b/i.test(opts.message) ||
      /解析|上传|工程/.test(opts.message);
    const progressId = parsing
      ? pushMsg(
          "system",
          "正在解析 PLC 工程：检测输入 → Openness/XML → PLC-IR → 逻辑图/知识图谱…",
        )
      : null;
    try {
      const turn = await postChatTurn({
        message: opts.message,
        taskId: activeId,
        file: opts.file,
        focusNodeId: opts.focusNodeId,
        blockName: opts.blockName,
        canvasEdges: canvas.edges.filter((e) => e.user_created),
        canvasPositions: canvas.nodes.map((n) => ({ id: n.id, x: n.x, y: n.y })),
      });
      const task = turn.task;
      const id = task.id;
      if (!id) throw new Error("未返回任务 ID");
      const topic: Topic = {
        id,
        title: titleFromQuery(task.query || display),
        status: String(task.status || ""),
        route: turn.route,
        plcJobId: turn.plc_job_id,
      };
      setTopics((prev) => [topic, ...prev.filter((t) => t.id !== id)]);
      setActiveId(id);
      setStatus(String(task.status || ""));
      setInterrupts((task.interrupts as Record<string, unknown>[]) || []);
      pushMsg("assistant", turn.assistant_message || "", {
        citations: attachCitationNodes(turn.citations, canvas.nodes),
      });
      const linked = turn.plc_job_id || task.plc_job_id;
      // Node deep-dive / describe: keep current galaxy; only hydrate chat/job text.
      const isNodeFocus = Boolean(opts.focusNodeId || opts.blockName);
      if (!isNodeFocus || canvasGalaxyScore(canvas) === 0) {
        const applied = applyCanvasFromTask(task, turn.knowledge_canvas);
        if (linked) {
          let detail = await hydratePlc(String(linked));
          if (detail.status !== "ready" && detail.status !== "failed") {
            detail = await waitForPlcJob(String(linked), {
              intervalMs: 1500,
              onProgress: (d) => {
                setPlcJob(d);
                const label = formatPlcProgress(d);
                setStatus(label);
                if (progressId) {
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === progressId ? { ...m, content: `正在解析 PLC 工程：${label}` } : m,
                    ),
                  );
                }
              },
            });
            setPlcJob(detail);
            setPlcJobId(detail.id);
          }
          if (progressId) {
            setMessages((prev) => prev.filter((m) => m.id !== progressId));
          }
          if (detail.status === "failed") {
            pushMsg("system", detail.error || "PLC 解析失败");
            setStatus("failed");
          } else if (detail.status === "ready") {
            setStatus("ready");
            const hasGalaxy = canvasGalaxyScore(applied) > 0 || canvasGalaxyScore(canvas) > 0;
            if (!applied?.nodes.length || !hasGalaxy) {
              applyCanvasFromPlcJob(detail);
            }
            const welcome = [...(detail.chat || [])]
              .reverse()
              .find((c) => c.role === "assistant");
            if (welcome?.content) {
              setMessages((prev) => {
                for (let i = prev.length - 1; i >= 0; i -= 1) {
                  if (prev[i].role === "assistant") {
                    const next = prev.slice();
                    next[i] = {
                      ...next[i],
                      content: welcome.content,
                      citations: attachCitationNodes(
                        welcome.citations || next[i].citations,
                        canvas.nodes,
                      ),
                    };
                    return next;
                  }
                }
                return prev;
              });
            }
          }
        } else {
          if (progressId) {
            setMessages((prev) => prev.filter((m) => m.id !== progressId));
          }
          if (turn.route === "research") connectWs(id);
        }
      } else if (linked) {
        if (progressId) {
          setMessages((prev) => prev.filter((m) => m.id !== progressId));
        }
        await hydratePlc(String(linked));
      } else {
        if (progressId) {
          setMessages((prev) => prev.filter((m) => m.id !== progressId));
        }
        if (turn.route === "research") connectWs(id);
      }
      void refreshTopics();
    } catch (err) {
      if (progressId) {
        setMessages((prev) => prev.filter((m) => m.id !== progressId));
      }
      const raw = err instanceof Error ? err.message : String(err);
      const expired =
        /SESSION_EXPIRED|会话已失效|Missing ['"]?tsk_|找不到 tsk_/i.test(raw) ||
        /找不到 job_/i.test(raw);
      if (expired) {
        const staleId = activeId;
        setActiveId(null);
        setPlcJob(null);
        setPlcJobId(null);
        setCanvas(emptyCanvas());
        if (staleId) {
          setTopics((prev) => prev.filter((t) => t.id !== staleId));
        }
        pushMsg(
          "system",
          raw.includes("会话已失效")
            ? raw
            : "会话已失效（Gateway 重启后内存任务已清空）。请点「新建」并重新上传工程后再提问。",
        );
      } else {
        pushMsg("system", raw);
      }
      setStatus("error");
    } finally {
      setBusy(false);
    }
  }

  async function onSend(e: FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if ((!text && !file) || busy) return;
    const attached = file;
    setDraft("");
    setFile(null);
    if (fileRef.current) fileRef.current.value = "";
    const fallback = text || `解析工程文件 ${attached?.name || ""}`.trim();
    const display = text || (attached ? `（上传 ${attached.name}）` : "");
    if (attached) {
      await sendTurn({
        message: fallback,
        file: attached,
        displayUser: display,
      });
      return;
    }
    const mentioned = mentionFromText(text);
    if (mentioned) {
      await sendTurn({
        message: fallback,
        file: attached,
        focusNodeId: chatScope?.nodeId,
        blockName: mentioned,
        displayUser: display,
        scopeLabel: mentioned,
      });
      return;
    }
    if (chatScope) {
      await sendTurn({
        message: `@${chatScope.blockName} ${fallback}`,
        file: attached,
        focusNodeId: chatScope.nodeId,
        blockName: chatScope.blockName,
        displayUser: display,
        scopeLabel: chatScope.label,
      });
      return;
    }
    await sendTurn({
      message: fallback,
      file: attached,
      displayUser: display,
    });
  }

  async function onDeepDive(node: KnowledgeNode, question: string) {
    applyChatScope(node);
    const scope = chatScopeFromNode(node);
    const block = scope.blockName;
    const q = question.trim();
    const message = block ? `@${block} ${q}` : q;
    await sendTurn({
      message,
      focusNodeId: node.id,
      blockName: block || null,
      displayUser: q,
      scopeLabel: scope.label || undefined,
    });
  }

  async function onOptimizePropose() {
    if (!plcJobId || busy) return;
    setBusy(true);
    try {
      const data = await optimizePlcJob(plcJobId, {
        message: "优化工程逻辑并准备反写",
        blockName:
          chatScope && chatScope.kind !== "plc_tag" ? chatScope.blockName : undefined,
      });
      const detail = await hydratePlc(plcJobId);
      const plan =
        String(detail.optimize_plan || data.optimize_plan || "").trim() ||
        "（无优化计划文本）";
      const opsFromCs = detail.changeset?.ops;
      const ops =
        typeof data.ops === "number"
          ? data.ops
          : Array.isArray(opsFromCs)
            ? opsFromCs.length
            : 0;
      const skipped = data.skipped || detail.scl_skipped || [];
      const diffs = data.scl_diffs || detail.scl_diffs || [];
      const skipLines = skipped
        .slice(0, 24)
        .map((s) => `- \`${s.block || "?"}\`：${s.reason || ""}${s.detail ? ` — ${s.detail}` : ""}`)
        .join("\n");
      const diffLines = diffs
        .slice(0, 8)
        .map((d) => {
          const body = String(d.diff || "").trim() || "(unchanged importable SCL)";
          return `#### \`${d.block || "?"}\`${d.new_block ? "（新建）" : ""}\n\n\`\`\`diff\n${body}\n\`\`\``;
        })
        .join("\n\n");
      const extra = [
        skipLines ? `### 跳过（拒绝写程序体）\n\n${skipLines}` : "",
        diffLines ? `### SCL diff\n\n${diffLines}` : "",
      ]
        .filter(Boolean)
        .join("\n\n");
      pushMsg(
        "assistant",
        `### 优化提案（HITL）\n\n已生成 **${ops}** 条变更操作（含 SCL 改写/解耦）。请审阅 **SCL diff** 与跳过列表后再点「确认反写.zap」。\n\n${plan}${extra ? `\n\n${extra}` : ""}`,
      );
      setStatus("optimize_proposed");
    } catch (err) {
      pushMsg("system", err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onConfirmWriteback() {
    if (!plcJobId || busy) return;
    let projectPath = String(plcJob?.project_path || "").trim();
    if (!projectPath) {
      const entered = window.prompt("请输入 TIA 工程路径（.ap19/.apxx）");
      if (entered == null) return;
      projectPath = entered.trim();
      if (!projectPath) {
        pushMsg("system", "需要工程路径才能确认反写");
        return;
      }
    }
    setBusy(true);
    try {
      const data = await writebackPlcJob(plcJobId, projectPath, {
        archiveZap: true,
      });
      const detail = await hydratePlc(plcJobId);
      const zap = String(
        (detail.writeback as { zap_path?: string } | null)?.zap_path ||
          data.zap_path ||
          "",
      );
      const compile = (data.compile ||
        (detail.writeback as { compile?: unknown } | null)?.compile ||
        (data.openness as { compile?: unknown } | null)?.compile) as
        | Record<string, unknown>
        | undefined;
      if (zap) {
        const name = String(zap).split(/[/\\]/).pop() || "archive.zap";
        pushMsg(
          "assistant",
          `### 反写完成\n\n编译通过后已归档 .zap：\`${zap}\`\n\n[${name}](${plcZapUrl(plcJobId)})`,
        );
      } else {
        const compileNote = compile
          ? `\n\n编译门禁：\`${JSON.stringify(compile)}\`。编译失败或 API 不可达时**不会**归档 .zap。`
          : "";
        pushMsg(
          "assistant",
          `### 反写结果\n\n\`\`\`json\n${JSON.stringify(
            { openness: data.openness, zap_archive: data.zap_archive || detail.writeback, compile },
            null,
            2,
          )}\n\`\`\`${compileNote}`,
        );
      }
      setStatus("writeback_done");
    } catch (err) {
      pushMsg("system", err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onResume(resolution: string) {
    if (!activeId) return;
    setBusy(true);
    try {
      await resumeTask(activeId, resolution);
      pushMsg("system", resolution);
      const body = await fetchTask(activeId);
      const task = unwrapTask(body);
      setStatus(String(task.status || ""));
      setInterrupts((task.interrupts as Record<string, unknown>[]) || []);
      applyCanvasFromTask(task);
    } catch (err) {
      pushMsg("system", err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onCancel() {
    if (!activeId) return;
    setBusy(true);
    try {
      await cancelTask(activeId);
      setStatus("cancelled");
      pushMsg("system", "已取消");
    } catch (err) {
      pushMsg("system", err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
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
        <aside
          className={`col history${historyCollapsed ? " collapsed" : ""}`}
          aria-label="历史话题"
          style={{ flex: `0 0 ${historyShownW}px`, width: historyShownW }}
        >
          {historyCollapsed ? (
            <button
              type="button"
              className="history-expand"
              title="展开历史栏"
              aria-label="展开历史栏"
              onClick={toggleHistoryCollapsed}
            >
              <span className="history-expand-label">历史</span>
            </button>
          ) : (
            <>
              <div className="col-head">
                <h2>历史</h2>
                <div className="col-head-actions">
                  <button
                    type="button"
                    className="ghost compact"
                    title="折叠历史栏"
                    aria-label="折叠历史栏"
                    onClick={toggleHistoryCollapsed}
                  >
                    «
                  </button>
                  {topics.length ? (
                    <button
                      type="button"
                      className="ghost compact"
                      title="清空全部历史"
                      onClick={() => void clearAllTopics()}
                    >
                      清空
                    </button>
                  ) : null}
                  <button type="button" className="ghost compact" onClick={startNew}>
                    新建
                  </button>
                </div>
              </div>
              <ul className="topic-list">
                {topics.length === 0 ? (
                  <li className="empty-li">暂无话题</li>
                ) : (
                  topics.map((t) => (
                    <li key={t.id} className="topic-row">
                      <button
                        type="button"
                        className={t.id === activeId ? "topic on" : "topic"}
                        onClick={() => void openTopic(t)}
                      >
                        <span className="topic-title">{t.title}</span>
                        <span className={`topic-meta tone-${statusTone(t.status)}`}>{t.status}</span>
                      </button>
                      <button
                        type="button"
                        className="topic-delete"
                        title="删除此对话"
                        aria-label={`删除 ${t.title}`}
                        onClick={(e) => void deleteTopic(t, e)}
                      >
                        ×
                      </button>
                    </li>
                  ))
                )}
              </ul>
            </>
          )}
        </aside>

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

        <main
          className="col chat"
          aria-label="当前对话"
          style={{ flex: `0 0 ${chatW}px`, width: chatW }}
        >
          <div className="col-head">
            <h2>对话</h2>
            {active ? <span className="muted col-head-title">{active.title}</span> : null}
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

            {messages.map((m) => (
              <div key={m.id} className={`bubble ${m.role}`}>
                <div className="bubble-meta">
                  <span className="bubble-time">{formatMsgTime(m.at)}</span>
                  <button
                    type="button"
                    className="bubble-copy"
                    onClick={() => void copyMessage(m)}
                    title="复制内容"
                  >
                    {copiedId === m.id ? "已复制" : "复制"}
                  </button>
                </div>
                <div className="bubble-body">
                  {m.role === "assistant" ? (
                    <>
                      <MarkdownBody content={m.content} />
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
                          void sendTurn({
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
                          void sendTurn({
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

            {interrupts.length > 0 ? (
              <div className="interrupt">
                <div className="row-actions">
                  <button type="button" disabled={busy} onClick={() => void onResume("approve")}>
                    批准
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    disabled={busy}
                    onClick={() => void onResume("reject")}
                  >
                    拒绝
                  </button>
                  <button type="button" className="ghost" disabled={busy} onClick={() => void onCancel()}>
                    取消
                  </button>
                </div>
              </div>
            ) : null}
            <div ref={chatEndRef} />
          </div>

          {chatScope ? (
            <div className="chat-scope-prompts" aria-label="针对当前节点的建议">
              {scopedPrompts(chatScope).map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="ghost compact"
                  disabled={busy}
                  onClick={() => {
                    const node = scopedNode();
                    if (node) void onDeepDive(node, prompt);
                  }}
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
                      onClick={() => {
                        const node = scopedNode();
                        if (node) void onDeepDive(node, chip);
                      }}
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
                          onClick={() => {
                            const node = scopedNode();
                            if (node) void onDeepDive(node, chip);
                          }}
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
                    onClick={clearChatScope}
                  >
                    ×
                  </button>
                </div>
              ) : null}
              <textarea
                ref={composerRef}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
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
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
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

        <section className="col canvas" aria-label="画布">
          <div className="col-head">
            <h2>画布</h2>
            <div className="col-head-actions">
              {plcJobId && plcJob?.status === "ready" ? (
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
                    title="确认 changeset 并 Openness 反写归档 .zap"
                    onClick={() => void onConfirmWriteback()}
                  >
                    确认反写.zap
                  </button>
                  {(plcJob?.writeback as { zap_path?: string } | null)?.zap_path ? (
                    <a
                      className="ghost compact"
                      href={plcZapUrl(plcJobId)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      下载.zap
                    </a>
                  ) : null}
                </>
              ) : null}
              {plcJobId && plcJob?.export_ready ? (
                <a className="ghost compact" href={plcExportUrl(plcJobId)} target="_blank" rel="noreferrer">
                  导出
                </a>
              ) : null}
            </div>
          </div>
          <div className="canvas-body canvas-kg">
            <PlcCoverageStrip detail={plcJob} />
            <KnowledgeCanvas
              data={canvas}
              logicGraph={
                plcJob?.logic_graph
                  ? {
                      nodes: (plcJob.logic_graph.nodes || []).map((n) => {
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
                      edges: (plcJob.logic_graph.edges || []).map((e) => ({
                        source: String(e.source || ""),
                        target: String(e.target || ""),
                        type: e.type ? String(e.type) : undefined,
                        seq: typeof e.seq === "number" ? e.seq : undefined,
                      })),
                    }
                  : null
              }
              knowledgeGraph={plcJob?.knowledge_graph || null}
              onChange={setCanvas}
              onDeepDive={onDeepDive}
              onSelectNode={applyChatScope}
              onAskInChat={onAskInChat}
              focusRequest={canvasFocus}
              busy={busy}
            />
          </div>
        </section>
      </div>

      {showSettings ? (
        <div className="modal-backdrop" role="presentation" onClick={() => setShowSettings(false)}>
          <div
            className="modal modal-settings"
            role="dialog"
            aria-label="设置"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-head">
              <h2>设置</h2>
              <button type="button" className="ghost" onClick={() => setShowSettings(false)}>
                关闭
              </button>
            </div>
            <SettingsPanel />
          </div>
        </div>
      ) : null}
    </div>
  );
}
