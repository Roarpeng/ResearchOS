import { useState } from "react";
import { GATEWAY_BASE, createResearchTask, fetchTask, unwrapTask } from "./api";

type Panels = {
  plan: string;
  evidence: string;
  result: string;
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

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    setStatus("正在创建研究任务…");
    setPanels(emptyPanels);
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
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatus(`创建失败：${msg}`);
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
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatus(`刷新失败：${msg}`);
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
          </div>
          <p className="status-line">
            {busy ? <span className="pulse-dot" aria-hidden /> : null}
            <strong>{status}</strong>
          </p>
        </form>

        <section className="panel panels-stack">
          <h2>任务视图</h2>
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
          <div className="panel-block">
            <h3>Result</h3>
            {panels.result ? (
              <pre className="mono">{panels.result}</pre>
            ) : (
              <p className="empty">Writer 成稿 Markdown 将显示在此</p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
