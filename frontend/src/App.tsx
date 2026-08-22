import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
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
  type PlcJobDetail,
} from "./api";
import { PlcCoverageStrip } from "./plc/CoverageStrip";
import {
  canvasGalaxyScore,
  emptyCanvas,
  normalizeCanvas,
  plcCanvasFromJob,
} from "./plc/canvasModel";
import {
  formatPlcProgress,
  formatWritebackRecap,
  sclDiffsForFocus,
  writebackHintForBlock,
} from "./plc/detail";
import KnowledgeCanvas, {
  autoLayoutKnowledge,
  type CanvasFocusRequest,
  type KnowledgeCanvasData,
  type KnowledgeNode,
} from "./KnowledgeCanvas";
import SettingsPanel from "./SettingsPanel";
import CitationRail from "./CitationRail";
import InterruptBar from "./InterruptBar";
import Timeline from "./Timeline";
import { ChatMessages } from "./workbench/ChatMessages";
import {
  attachCitationNodes,
  chatScopeFromNode,
  isPlcScopeNode,
  mentionFromText,
  pretty,
  NESTED_CHIPS,
  ROLE_CHIPS,
  titleFromQuery,
  type ChatMsg,
  type ChatScope,
  type Topic,
} from "./workbench/model";
import { statusTone } from "./workbench/layout";
import { useTriSplit } from "./workbench/useTriSplit";
import {
  mergeCitations,
  mergeEvents,
  mergeInterrupts,
} from "./workbench/collections";
import {
  collectCitations,
  collectEvents,
  collectInterrupts,
  normalizeCitations,
  normalizeEvent,
  normalizeInterrupts,
  type CitationItem,
  type InterruptItem,
  type ResearchEvent,
} from "./researchModel";

export default function App() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [plcJobId, setPlcJobId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [draft, setDraft] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [interrupts, setInterrupts] = useState<InterruptItem[]>([]);
  const [plcJob, setPlcJob] = useState<PlcJobDetail | null>(null);
  const [canvas, setCanvas] = useState<KnowledgeCanvasData>(emptyCanvas);
  const [showSettings, setShowSettings] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [chatScope, setChatScope] = useState<ChatScope | null>(null);
  const [canvasFocus, setCanvasFocus] = useState<CanvasFocusRequest | null>(null);
  const [events, setEvents] = useState<ResearchEvent[]>([]);
  const [citations, setCitations] = useState<CitationItem[]>([]);
  const [canvasTab, setCanvasTab] = useState<"canvas" | "timeline" | "citations">("canvas");
  const wsRef = useRef<WebSocket | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);
  const {
    chatW,
    historyCollapsed,
    historyShownW,
    onTriSplitPointerDown,
    resetTriSplit,
    toggleHistoryCollapsed,
    triRef,
  } = useTriSplit();

  const active = topics.find((t) => t.id === activeId) || null;

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
      : ["这个块干什么", "展开 SCL", "分析逻辑", "嵌套链", "理解逻辑", "优化逻辑", "优化SCL", "确认反写", "谁调用它 / 它调用谁", "谁读写这些信号", "优化建议"];
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
    setEvents([]);
    setCitations([]);
    setCanvasTab("canvas");
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
    const next = plcCanvasFromJob(detail);
    if (next) setCanvas(next);
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
    setEvents([]);
    setCitations([]);
    setCanvasTab("canvas");
    try {
      const body = await fetchTask(topic.id);
      const task = unwrapTask(body);
      const result = (task.result || {}) as Record<string, unknown>;
      const linked =
        task.plc_job_id ||
        (typeof result.plc_job_id === "string" ? result.plc_job_id : null);
      setStatus(String(task.status || ""));
      setInterrupts(collectInterrupts(task));
      setEvents(collectEvents(task));
      setCitations(collectCitations(task));
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
      const ev = normalizeEvent(event);
      if (ev) setEvents((prev) => mergeEvents(prev, [ev]));
      if (etype === "task.status") setStatus(String(payload.status || ""));
      if (etype === "interrupt.required" || etype === "interrupt") {
        setInterrupts((prev) =>
          mergeInterrupts(prev, normalizeInterrupts([payload]).filter((x) => !x.resolved)),
        );
      }
      if (etype === "interrupt.resolved" || etype === "interrupt_resolved") {
        setInterrupts([]);
      }
      if (etype === "citation.added" || etype === "citation") {
        setCitations((prev) => mergeCitations(prev, normalizeCitations([payload])));
      }
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
      setInterrupts(collectInterrupts(task));
      setEvents((prev) => mergeEvents(prev, collectEvents(task)));
      setCitations((prev) => mergeCitations(prev, collectCitations(task)));
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
        `### 优化提案（HITL）\n\n已生成 **${ops}** 条变更操作（含 SCL 改写/解耦）。请审阅 **SCL diff** 与跳过列表后再点节点「确认反写」或画布「确认反写.zap」。\n\n${plan}${extra ? `\n\n${extra}` : ""}`,
      );
      setStatus("optimize_proposed");
    } catch (err) {
      pushMsg("system", err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onConfirmWriteback(blockName?: string | null) {
    if (!plcJobId || busy) return;
    const focus = String(blockName || "").trim() || undefined;
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
        blockName: focus || null,
      });
      const detail = await hydratePlc(plcJobId);
      const recap = formatWritebackRecap(data, detail, focus);
      const zap = String(
        (detail.writeback as { zap_path?: string } | null)?.zap_path ||
          data.zap_path ||
          "",
      );
      if (zap) {
        const name = String(zap).split(/[/\\]/).pop() || "archive.zap";
        pushMsg("assistant", `${recap}\n\n[${name}](${plcZapUrl(plcJobId)})`);
      } else {
        pushMsg("assistant", recap.trim() ? recap : "### 确认反写\n未返回导入/编译/归档结果。");
      }
      setStatus("writeback_done");
    } catch (err) {
      pushMsg("system", err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onResume(resolution: string, interruptId?: string) {
    if (!activeId) return;
    setBusy(true);
    try {
      await resumeTask(activeId, resolution, interruptId);
      pushMsg("system", resolution);
      const body = await fetchTask(activeId);
      const task = unwrapTask(body);
      setStatus(String(task.status || ""));
      setInterrupts(collectInterrupts(task));
      setEvents((prev) => mergeEvents(prev, collectEvents(task)));
      setCitations((prev) => mergeCitations(prev, collectCitations(task)));
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
            <ChatMessages
              messages={messages}
              copiedId={copiedId}
              busy={busy}
              plcJob={plcJob}
              chatScope={chatScope}
              onCopyMessage={copyMessage}
              onFocusNode={onFocusNode}
              onSendTurn={sendTurn}
            />

            {interrupts.length > 0 ? (
              <InterruptBar
                interrupts={interrupts}
                busy={busy}
                onResolve={(id, resolution) => void onResume(resolution, id)}
                onCancel={() => void onCancel()}
              />
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

        <section className="col canvas" aria-label="研究视图">
          <div className="col-head">
            <div className="canvas-tabs" role="tablist" aria-label="研究视图">
              <button
                type="button"
                className={canvasTab === "canvas" ? "on" : ""}
                onClick={() => setCanvasTab("canvas")}
              >
                画布
              </button>
              <button
                type="button"
                className={canvasTab === "timeline" ? "on" : ""}
                onClick={() => setCanvasTab("timeline")}
              >
                时间线
              </button>
              <button
                type="button"
                className={canvasTab === "citations" ? "on" : ""}
                onClick={() => setCanvasTab("citations")}
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
                      chatScope && chatScope.kind !== "plc_tag"
                        ? `确认 ${chatScope.label} 的 changeset 并 Openness 反写归档 .zap`
                        : "确认整工程 changeset 并 Openness 反写归档 .zap"
                    }
                    onClick={() =>
                      void onConfirmWriteback(
                        chatScope && chatScope.kind !== "plc_tag"
                          ? chatScope.blockName
                          : undefined,
                      )
                    }
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
              onConfirmWriteback={(node) => {
                const name = String(node.source?.block_name || node.label || "").trim();
                return onConfirmWriteback(name || undefined);
              }}
              writebackHint={(blockName) => writebackHintForBlock(plcJob, blockName)}
              getSclPreview={(blockName) => sclDiffsForFocus(plcJob, blockName)}
              onSelectNode={applyChatScope}
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
