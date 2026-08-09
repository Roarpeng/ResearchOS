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
  postChatTurn,
  resumeTask,
  unwrapTask,
  type PlcJobDetail,
} from "./api";
import KnowledgeCanvas, {
  autoLayoutKnowledge,
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

type ChatMsg = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  at: number;
};

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
  const wsRef = useRef<WebSocket | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
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

  function pushMsg(role: ChatMsg["role"], content: string) {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const at = Date.now();
    setMessages((prev) => [...prev, { id, role, content, at }]);
    return id;
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
    const want = new Set(["CALLS", "USES", "INSTANCE_OF", "DEPENDS_ON"]);
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
      const kind =
        btype === "OB" ? "plc_ob" : btype === "DB" ? "plc_db" : "plc_block";
      const inst = String(b.instance_of || "").trim();
      const bits = [btype];
      if (b.language) bits.push(String(b.language));
      if (b.networks != null) bits.push(`${b.networks} 网络`);
      if (inst) bits.push(`实例←${inst}`);
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
      nodes.push({
        id: `plc_b_${detail.id}_${name}`,
        label: name,
        summary: `${btype} · 由依赖引用补全`,
        kind: btype === "OB" ? "plc_ob" : btype === "DB" ? "plc_db" : "plc_block",
        x: 0,
        y: 0,
        source: {
          type: "plc",
          plc_job_id: detail.id,
          block_name: name,
          block_type: btype,
          project: detail.project_name,
        },
      });
    }
    const byLabel = new Map<string, string>();
    nodes.forEach((n) => {
      byLabel.set(n.label, n.id);
      byLabel.set(`Block::${n.label}`, n.id);
    });
    // Knowledge galaxy: CALLS / USES / INSTANCE_OF / DEPENDS_ON (full KG)
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
        return t === "CALLS" || t === "USES" || t === "INSTANCE_OF" || t === "DEPENDS_ON";
      })
      .slice()
      .sort((a, b) => {
        const rank: Record<string, number> = {
          CALLS: 0,
          USES: 1,
          INSTANCE_OF: 2,
          DEPENDS_ON: 3,
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
        const detail = await hydratePlc(linked);
        if (detail.chat?.length) {
          const base = Date.now();
          setMessages(
            detail.chat.map((c, i) => ({
              id: `c${i}`,
              role: c.role === "user" ? "user" : "assistant",
              content: c.content,
              at: base + i,
            })),
          );
        }
        // Always rebuild star from job so legacy grid canvases get fixed.
        if (detail.status === "ready") applyCanvasFromPlcJob(detail);
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
  }) {
    setBusy(true);
    const display = opts.displayUser || opts.message;
    if (display) pushMsg("user", display);
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
      if (progressId) {
        setMessages((prev) => prev.filter((m) => m.id !== progressId));
      }
      pushMsg("assistant", turn.assistant_message || "");
      const linked = turn.plc_job_id || task.plc_job_id;
      // Node deep-dive / describe: keep current galaxy; only hydrate chat/job text.
      const isNodeFocus = Boolean(opts.focusNodeId || opts.blockName);
      if (!isNodeFocus || canvasGalaxyScore(canvas) === 0) {
        const applied = applyCanvasFromTask(task, turn.knowledge_canvas);
        if (linked) {
          const detail = await hydratePlc(String(linked));
          const hasGalaxy = canvasGalaxyScore(applied) > 0 || canvasGalaxyScore(canvas) > 0;
          if (detail.status === "ready" && (!applied?.nodes.length || !hasGalaxy)) {
            applyCanvasFromPlcJob(detail);
          }
        } else if (turn.route === "research") connectWs(id);
      } else if (linked) {
        await hydratePlc(String(linked));
      } else if (turn.route === "research") connectWs(id);
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
    await sendTurn({
      message: text || `解析工程文件 ${attached?.name || ""}`.trim(),
      file: attached,
      displayUser: text || (attached ? `（上传 ${attached.name}）` : ""),
    });
  }

  async function onDeepDive(node: KnowledgeNode, question: string) {
    const block =
      node.source?.block_name ||
      (node.kind === "plc_block" ? node.label : "") ||
      "";
    const q = question.trim();
    const message = block ? `@${block} ${q}` : q;
    await sendTurn({
      message,
      focusNodeId: node.id,
      blockName: block || null,
      displayUser: message,
    });
  }

  async function onNodeDescribe(node: KnowledgeNode) {
    await onDeepDive(node, "请描述这个功能块的作用、输入输出与主要逻辑");
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
                    <MarkdownBody content={m.content} />
                  ) : (
                    m.content
                  )}
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

          <form className="composer composer-plc" onSubmit={onSend}>
            <div className="composer-main">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="需要探索什么吗？"
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
            {plcJobId && plcJob?.export_ready ? (
              <a className="ghost compact" href={plcExportUrl(plcJobId)} target="_blank" rel="noreferrer">
                导出
              </a>
            ) : null}
          </div>
          <div className="canvas-body canvas-kg">
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
              onChange={setCanvas}
              onDeepDive={onDeepDive}
              onNodeDescribe={onNodeDescribe}
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
