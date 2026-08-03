import { useState, useEffect, useRef } from "react";
import {
  GATEWAY_BASE,
  createResearchTask,
  fetchTask,
  resumeTask,
  cancelTask,
  unwrapTask,
  connectResearchStream,
} from "./api";

type Panels = {
  plan: string;
  evidence: string;
  result: string;
};

type TimelineEvent = {
  ts: string;
  type: string;
  detail: string;
};

type Citation = {
  id: string;
  title: string;
  url: string;
  quote?: string;
};

const emptyPanels: Panels = {
  plan: "",
  evidence: "",
  result: "",
};

function pretty(value: unknown): string {
  if (value == null || value === "") return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export default function App() {
  const [query, setQuery] = useState(
    "对比协作机器人在力控与安全认证上的差异，并给出选型建议",
  );
  const [mode, setMode] = useState("deep");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("就绪 — 连接到 Gateway 后创建任务");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [panels, setPanels] = useState<Panels>(emptyPanels);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [interrupts, setInterrupts] = useState<Record<string, unknown>[]>([]);
  const [showMarkdown, setShowMarkdown] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  function addTimeline(type: string, detail: string) {
    setTimeline((prev: TimelineEvent[]) => [
      ...prev,
      { ts: new Date().toISOString(), type, detail },
    ]);
  }

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  function connectWs(id: string) {
    wsRef.current?.close();
    const ws = connectResearchStream(
      id,
      (event) => {
        const etype = (event.event_type || event.type || "unknown") as string;
        const payload = (event.payload || {}) as Record<string, unknown>;
        addTimeline(etype, JSON.stringify(payload).slice(0, 200));
        if (etype === "task.status") {
          setStatus(`状态: ${payload.status}`);
        }
      },
    );
    wsRef.current = ws;
  }

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    setStatus("正在创建研究任务…");
    setPanels(emptyPanels);
    setTimeline([]);
    setCitations([]);
    setInterrupts([]);
    try {
      const created = await createResearchTask(query.trim(), mode);
      const task = unwrapTask(created);
      const id = task.id;
      if (!id) throw new Error("响应缺少 task id");
      setTaskId(id);
      setPanels({
        plan: pretty(task.plan) || "（计划尚未返回 — Gateway/Runtime 就绪后将显示）",
        evidence: pretty(task.evidence) || "（证据池为空）",
        result: pretty(task.result) || "（报告尚未生成）",
      });
      setStatus(`任务已创建：${id}（${task.status ?? "queued"}）`);
      addTimeline("task.created", `id=${id} status=${task.status}`);

      // Extract citations from result data
      const resultData = task.result as Record<string, unknown> | null;
      if (resultData) {
        const cites = (resultData.citations || []) as Citation[];
        setCitations(cites);
        const evts = (resultData.events || []) as Record<string, unknown>[];
        for (const ev of evts) {
          addTimeline(
            String(ev.type || "event"),
            JSON.stringify(ev).slice(0, 200),
          );
        }
        const intrs = (resultData.interrupts || []) as Record<string, unknown>[];
        setInterrupts(intrs);
      }

      // Connect WebSocket for live updates
      connectWs(id);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatus(`创建失败：${msg}`);
      addTimeline("error", msg);
      setPanels({
        plan: "",
        evidence: "",
        result:
          "Gateway 不可达或尚未实现 Phase 2 API。\n" +
          "请确认 http://localhost:8000 已启动，或设置 VITE_GATEWAY_URL。",
      });
    } finally {
      setBusy(false);
    }
  }

  async function onRefresh() {
    if (!taskId) return;
    setBusy(true);
    setStatus(`刷新任务 ${taskId}…`);
    try {
      const body = await fetchTask(taskId);
      const task = unwrapTask(body);
      setPanels({
        plan: pretty(task.plan) || "（无计划）",
        evidence: pretty(task.evidence) || "（无证据）",
        result: pretty(task.result) || "（无报告）",
      });
      setStatus(`状态：${task.status ?? "unknown"}`);
      addTimeline("task.refreshed", `status=${task.status}`);

      const resultData = task.result as Record<string, unknown> | null;
      if (resultData) {
        const cites = (resultData.citations || []) as Citation[];
        if (cites.length) setCitations(cites);
        const intrs = (resultData.interrupts || []) as Record<string, unknown>[];
        setInterrupts(intrs);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatus(`刷新失败：${msg}`);
    } finally {
      setBusy(false);
    }
  }

  async function onResume(resolution: string) {
    if (!taskId) return;
    setBusy(true);
    try {
      await resumeTask(taskId, resolution);
      addTimeline("resume.sent", `resolution=${resolution}`);
      setStatus(`已发送 ${resolution}，继续执行…`);
      await onRefresh();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatus(`Resume 失败：${msg}`);
    } finally {
      setBusy(false);
    }
  }

  async function onCancel() {
    if (!taskId) return;
    setBusy(true);
    try {
      await cancelTask(taskId);
      addTimeline("task.cancelled", "");
      setStatus("任务已取消");
      await onRefresh();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatus(`取消失败：${msg}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="brand-hero">
        <h1 className="brand-mark">
          Research<span>OS</span>
        </h1>
        <p className="lede">
          自主深度研究控制台 — 计划、证据与带引用的报告在同一时间线可见。
        </p>
        <p className="gateway">
          Gateway: <code>{GATEWAY_BASE || "http://localhost:8000 (via /api proxy)"}</code>
        </p>
      </header>

      <div className="layout">
        <form className="panel" onSubmit={onCreate}>
          <h2>新建研究</h2>
          <div className="field">
            <label htmlFor="query">研究问题</label>
            <textarea
              id="query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="描述你的调研目标、范围与约束…"
              required
            />
          </div>
          <div className="field">
            <label htmlFor="mode">模式</label>
            <select
              id="mode"
              value={mode}
              onChange={(e) => setMode(e.target.value)}
            >
              <option value="quick">quick</option>
              <option value="deep">deep</option>
              <option value="industrial">industrial</option>
            </select>
          </div>
          <div className="actions">
            <button className="btn btn-primary" type="submit" disabled={busy}>
              {busy ? "处理中…" : "创建任务"}
            </button>
            <button
              className="btn btn-ghost"
              type="button"
              onClick={onRefresh}
              disabled={busy || !taskId}
            >
              刷新状态
            </button>
            <button
              className="btn btn-ghost"
              type="button"
              onClick={onCancel}
              disabled={busy || !taskId}
              style={{ marginLeft: "auto" }}
            >
              取消任务
            </button>
          </div>
          <p className="status-line">
            {busy ? <span className="pulse-dot" aria-hidden /> : null}
            <strong>{status}</strong>
          </p>
        </form>

        <section className="panel panels-stack">
          <h2>任务视图</h2>

          {/* HITL Interrupt Controls */}
          {interrupts.length > 0 && (
            <div className="panel-block" style={{ borderLeft: "3px solid #f59e0b" }}>
              <h3>⚠ 人工审批 (HITL)</h3>
              {interrupts.map((intr, idx) => (
                <div key={idx} style={{ marginBottom: "8px" }}>
                  <p><strong>{String(intr.kind || "interrupt")}</strong>: {String(intr.prompt || "")}</p>
                  <div className="actions" style={{ gap: "4px" }}>
                    <button className="btn btn-primary" onClick={() => onResume("approve")} disabled={busy}>
                      批准
                    </button>
                    <button className="btn btn-ghost" onClick={() => onResume("edit")} disabled={busy}>
                      编辑
                    </button>
                    <button className="btn btn-ghost" onClick={() => onResume("abort")} disabled={busy}>
                      中止
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="panel-block">
            <h3>Plan</h3>
            {panels.plan ? (
              <pre className="mono">{panels.plan}</pre>
            ) : (
              <p className="empty">创建任务后显示计划步骤</p>
            )}
          </div>
          <div className="panel-block">
            <h3>Evidence</h3>
            {panels.evidence ? (
              <pre className="mono">{panels.evidence}</pre>
            ) : (
              <p className="empty">证据将随 Research Agent 追加</p>
            )}
          </div>

          {/* Citations */}
          {citations.length > 0 && (
            <div className="panel-block">
              <h3>引用 ({citations.length})</h3>
              <ul style={{ listStyle: "none", padding: 0 }}>
                {citations.map((cit, idx) => (
                  <li key={idx} style={{ marginBottom: "6px", padding: "4px 8px", background: "#1e293b", borderRadius: "4px" }}>
                    <strong>[{cit.id}]</strong>{" "}
                    {cit.url ? (
                      <a href={cit.url} target="_blank" rel="noreferrer" style={{ color: "#60a5fa" }}>
                        {cit.title || cit.url}
                      </a>
                    ) : (
                      <span>{cit.title || "untitled"}</span>
                    )}
                    {cit.quote && <p style={{ margin: "2px 0 0", fontSize: "0.85em", opacity: 0.7 }}>"{cit.quote.slice(0, 120)}"</p>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Result with Markdown toggle */}
          <div className="panel-block">
            <h3>
              Result
              {panels.result && (
                <button
                  className="btn btn-ghost"
                  onClick={() => setShowMarkdown(!showMarkdown)}
                  style={{ float: "right", fontSize: "0.8em", padding: "2px 8px" }}
                >
                  {showMarkdown ? "Raw" : "Rendered"}
                </button>
              )}
            </h3>
            {panels.result ? (
              showMarkdown ? (
                <div
                  className="markdown-body mono"
                  style={{ whiteSpace: "pre-wrap", lineHeight: 1.6 }}
                  dangerouslySetInnerHTML={{ __html: simpleMarkdown(panels.result) }}
                />
              ) : (
                <pre className="mono">{panels.result}</pre>
              )
            ) : (
              <p className="empty">Writer 成稿 Markdown 将显示在此</p>
            )}
          </div>

          {/* Timeline */}
          {timeline.length > 0 && (
            <div className="panel-block">
              <h3>事件时间线 ({timeline.length})</h3>
              <div style={{ maxHeight: "200px", overflowY: "auto" }}>
                {timeline.map((ev, idx) => (
                  <div key={idx} style={{ fontSize: "0.85em", padding: "2px 0", borderBottom: "1px solid #334155" }}>
                    <span style={{ opacity: 0.5 }}>{ev.ts.slice(11, 19)}</span>{" "}
                    <strong>{ev.type}</strong>{" "}
                    <span style={{ opacity: 0.7 }}>{ev.detail}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

/** Minimal Markdown to HTML for report rendering. */
function simpleMarkdown(md: string): string {
  return md
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/^- (.+)$/gm, "<li>$1</li>")
    .replace(/\[citation:([^\]]+)\]/g, '<span style="color:#60a5fa">[$1]</span>')
    .replace(/\[\^([^\]]+)\]/g, '<sup style="color:#60a5fa">[$1]</sup>')
    .replace(/^---$/gm, "<hr/>")
    .replace(/\n\n/g, "<br/><br/>");
}
