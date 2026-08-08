import { useEffect, useState, type FormEvent } from "react";
import {
  createKnowledgeSpace,
  fetchAgentWorkspace,
  fetchKnowledgeGraph,
  fetchKnowledgeStats,
  installMcpFromHub,
  installSkillFromHub,
  listKnowledgeSpaces,
  rebuildKnowledgeSpace,
  searchKnowledge,
  searchMcpHub,
  searchSkillsHub,
  updateAgentWorkspace,
  uploadKnowledgeDocument,
  type AgentToolItem,
  type AgentWorkspaceSettings,
  type HubMcpItem,
  type HubSkillItem,
  type KnowledgeSpace,
  type KnowledgeStats,
  type McpServerItem,
  type SkillItem,
} from "./api";
import LlmSettingsPanel from "./LlmSettingsPanel";

type TabId = "llm" | "knowledge" | "tools" | "mcp";

const TABS: Array<{ id: TabId; label: string }> = [
  { id: "llm", label: "LLM" },
  { id: "knowledge", label: "知识库" },
  { id: "tools", label: "Agent 工具" },
  { id: "mcp", label: "MCP / Skill" },
];

export default function SettingsPanel() {
  const [tab, setTab] = useState<TabId>("llm");

  return (
    <div className="settings-shell">
      <nav className="settings-tabs" aria-label="设置分类">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={tab === t.id ? "settings-tab on" : "settings-tab"}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>
      <div className="settings-body">
        {tab === "llm" ? <LlmSettingsPanel /> : null}
        {tab === "knowledge" ? <KnowledgeSettingsPanel /> : null}
        {tab === "tools" ? <AgentToolsPanel /> : null}
        {tab === "mcp" ? <McpSkillPanel /> : null}
      </div>
    </div>
  );
}

function KnowledgeSettingsPanel() {
  const [spaces, setSpaces] = useState<KnowledgeSpace[]>([]);
  const [activeId, setActiveId] = useState("");
  const [name, setName] = useState("默认知识库");
  const [desc, setDesc] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [stats, setStats] = useState<KnowledgeStats | null>(null);
  const [graphHint, setGraphHint] = useState("");
  const [searchQ, setSearchQ] = useState("");
  const [searchHits, setSearchHits] = useState<
    Array<{ citation_id: string; score: number; text: string; source_id: string }>
  >([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");

  async function refreshStats(id: string) {
    if (!id) return;
    try {
      const s = await fetchKnowledgeStats(id);
      setStats(s);
      const g = await fetchKnowledgeGraph(id);
      const n = (g.nodes || []).length;
      const e = (g.edges || []).length;
      setGraphHint(`图谱快照：${n} 实体 / ${e} 关系`);
    } catch {
      /* ignore */
    }
  }

  async function load() {
    setBusy(true);
    try {
      let list = await listKnowledgeSpaces();
      if (!list.length) {
        const created = await createKnowledgeSpace("默认知识库", "解析→分块→向量/BM25/图谱→对话召回");
        list = [created];
      }
      setSpaces(list);
      const id = activeId || list[0]?.id || "";
      setActiveId(id);
      await refreshStats(id);
      setStatus(`流水线：解析 → 语义分块 → 实体抽取 → Hybrid(RRF) 召回`);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (activeId) void refreshStats(activeId);
  }, [activeId]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      const space = await createKnowledgeSpace(name.trim(), desc.trim() || undefined);
      setSpaces((prev) => [space, ...prev]);
      setActiveId(space.id);
      setName("");
      setDesc("");
      setStatus(`已创建 ${space.name}`);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onUpload(e: FormEvent) {
    e.preventDefault();
    if (!activeId || !file) return;
    setBusy(true);
    try {
      const res = await uploadKnowledgeDocument(activeId, file);
      setStatus(
        `入库完成：${res.title || file.name} · ${res.status} · chunks ${res.chunk_count} · entities ${res.entity_count}`,
      );
      setFile(null);
      await load();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onRebuild() {
    if (!activeId) return;
    setBusy(true);
    try {
      const r = await rebuildKnowledgeSpace(activeId);
      setStatus(`索引已重建：${r.chunk_count} chunks` + (r.warnings?.length ? `（${r.warnings[0]}）` : ""));
      await refreshStats(activeId);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onSearch(e: FormEvent) {
    e.preventDefault();
    if (!searchQ.trim() || !activeId) return;
    setBusy(true);
    try {
      const res = await searchKnowledge(searchQ.trim(), [activeId], 6);
      setSearchHits(res.hits || []);
      setStatus(res.message || `召回 ${res.hits?.length || 0} 条`);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const active = spaces.find((s) => s.id === activeId) || spaces[0];

  return (
    <div className="settings-section">
      <div className="panel settings-panel-block">
        <div className="panel-head">
          <h2>知识空间</h2>
        </div>
        <p className="hint">文档解析 → 分块/嵌入 → 图谱抽取 → 对话 Hybrid 召回（向量+BM25+图 RRF）。</p>
        <form onSubmit={onCreate}>
          <div className="field">
            <label htmlFor="kb-name">名称</label>
            <input id="kb-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="kb-desc">说明</label>
            <input id="kb-desc" value={desc} onChange={(e) => setDesc(e.target.value)} />
          </div>
          <div className="actions">
            <button className="btn btn-primary" type="submit" disabled={busy || !name.trim()}>
              创建
            </button>
            <button className="btn btn-ghost" type="button" disabled={busy} onClick={() => void load()}>
              刷新
            </button>
          </div>
        </form>
        <div className="field" style={{ marginTop: "0.75rem" }}>
          <label htmlFor="kb-space">当前空间</label>
          <select id="kb-space" value={active?.id || ""} onChange={(e) => setActiveId(e.target.value)}>
            {spaces.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}（{s.document_count} 份）
              </option>
            ))}
          </select>
        </div>
        {stats ? (
          <p className="hint">
            文档 {stats.document_count} · 分块 {stats.chunk_count} · 实体 {stats.entity_count} · 关系{" "}
            {stats.relation_count}
            {graphHint ? ` · ${graphHint}` : ""}
          </p>
        ) : null}
        <form className="upload-row" onSubmit={onUpload}>
          <input
            type="file"
            accept=".pdf,.txt,.md,.docx,.doc,.csv,.json,.xml,.html"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          <button className="btn btn-primary" type="submit" disabled={busy || !file || !active}>
            上传并建图
          </button>
          <button className="btn btn-ghost" type="button" disabled={busy || !active} onClick={() => void onRebuild()}>
            重建索引
          </button>
        </form>
        <ul className="settings-list">
          {(active?.documents || stats?.documents || []).length === 0 ? (
            <li className="muted">暂无资料 — 上传后自动解析并入图</li>
          ) : (
            (active?.documents || []).map((d) => (
              <li key={d.id}>
                <strong>{d.title || d.filename || d.id}</strong>
                <span className="muted">
                  {d.status}
                  {d.chunk_count ? ` · ${d.chunk_count} chunks` : ""}
                </span>
              </li>
            ))
          )}
        </ul>
      </div>

      <section className="panel settings-panel-block">
        <div className="panel-head">
          <h2>召回试探</h2>
        </div>
        <p className="hint">模拟对话回复前的知识库召回（Hybrid RRF）。</p>
        <form className="settings-add-grid" onSubmit={onSearch}>
          <input
            placeholder="输入问题，例如：扭矩规格"
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
          />
          <button className="btn btn-primary" type="submit" disabled={busy || !searchQ.trim()}>
            检索
          </button>
        </form>
        <ul className="settings-list">
          {searchHits.length === 0 ? (
            <li className="muted">尚无命中</li>
          ) : (
            searchHits.map((h) => (
              <li key={`${h.citation_id}-${h.score}`}>
                <span>
                  <strong>{h.source_id}</strong>
                  <span className="muted"> · {h.score.toFixed(3)}</span>
                  <div className="muted">{h.text}</div>
                </span>
              </li>
            ))
          )}
        </ul>
        <p className="status-line">{status}</p>
      </section>
    </div>
  );
}

function AgentToolsPanel() {
  const [tools, setTools] = useState<AgentToolItem[]>([]);
  const [draft, setDraft] = useState({ name: "", description: "", command: "" });
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");

  async function load() {
    setBusy(true);
    try {
      const data = await fetchAgentWorkspace();
      setTools(data.tools || []);
      setStatus("已加载工具");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function persist(next: AgentToolItem[]) {
    setBusy(true);
    try {
      const data = await updateAgentWorkspace({ tools: next });
      setTools(data.tools || []);
      setStatus("已保存");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onAdd(e: FormEvent) {
    e.preventDefault();
    if (!draft.name.trim()) return;
    const next = [
      {
        id: `tool_${Date.now().toString(36)}`,
        name: draft.name.trim(),
        description: draft.description.trim(),
        command: draft.command.trim(),
        enabled: true,
      },
      ...tools,
    ];
    setDraft({ name: "", description: "", command: "" });
    await persist(next);
  }

  return (
    <div className="settings-section single">
      <section className="panel settings-panel-block">
        <div className="panel-head">
          <h2>Agent 工具</h2>
        </div>
        <p className="hint">启用或添加 Agent 可调用的工具（含 knowledge_search）。</p>
        <form className="settings-add-grid" onSubmit={onAdd}>
          <input
            placeholder="工具名"
            value={draft.name}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          />
          <input
            placeholder="说明"
            value={draft.description}
            onChange={(e) => setDraft({ ...draft, description: e.target.value })}
          />
          <input
            placeholder="命令 / 入口（可选）"
            value={draft.command}
            onChange={(e) => setDraft({ ...draft, command: e.target.value })}
          />
          <button className="btn btn-primary" type="submit" disabled={busy || !draft.name.trim()}>
            添加
          </button>
        </form>
        <ul className="settings-list">
          {tools.map((t) => (
            <li key={t.id || t.name}>
              <label className="settings-check">
                <input
                  type="checkbox"
                  checked={!!t.enabled}
                  disabled={busy}
                  onChange={(e) => {
                    const next = tools.map((x) =>
                      (x.id || x.name) === (t.id || t.name) ? { ...x, enabled: e.target.checked } : x,
                    );
                    void persist(next);
                  }}
                />
                <span>
                  <strong>{t.name}</strong>
                  {t.description ? <span className="muted"> — {t.description}</span> : null}
                </span>
              </label>
              <button
                type="button"
                className="ghost compact"
                disabled={busy}
                onClick={() => void persist(tools.filter((x) => (x.id || x.name) !== (t.id || t.name)))}
              >
                删除
              </button>
            </li>
          ))}
        </ul>
        <p className="status-line">{status}</p>
      </section>
    </div>
  );
}

function McpSkillPanel() {
  const [data, setData] = useState<AgentWorkspaceSettings | null>(null);
  const [mcpQ, setMcpQ] = useState("filesystem");
  const [skillQ, setSkillQ] = useState("docx");
  const [mcpHits, setMcpHits] = useState<HubMcpItem[]>([]);
  const [skillHits, setSkillHits] = useState<HubSkillItem[]>([]);
  const [hubNote, setHubNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");

  async function load() {
    setBusy(true);
    try {
      setData(await fetchAgentWorkspace());
      setStatus("已加载已安装 MCP / Skill");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function persist(patch: Partial<AgentWorkspaceSettings>) {
    setBusy(true);
    try {
      setData(await updateAgentWorkspace(patch));
      setStatus("已保存");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onSearchMcp(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await searchMcpHub(mcpQ.trim());
      setMcpHits(res.items || []);
      setHubNote(
        `${res.hub || "mcp-registry"}${res.offline ? "（离线目录）" : ""}${res.warning ? ` · ${res.warning}` : ""}`,
      );
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onSearchSkills(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await searchSkillsHub(skillQ.trim());
      setSkillHits(res.items || []);
      setHubNote(
        `${res.hub || "skills.sh"}${res.offline ? "（离线目录）" : ""}${res.warning ? ` · ${res.warning}` : ""}`,
      );
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const mcp = data?.mcp_servers || [];
  const skills = data?.skills || [];

  return (
    <div className="settings-section">
      <section className="panel settings-panel-block">
        <div className="panel-head">
          <h2>MCP Hub</h2>
        </div>
        <p className="hint">对接官方 registry.modelcontextprotocol.io，搜索后一键安装到工作区。</p>
        <form className="settings-add-grid" onSubmit={onSearchMcp}>
          <input value={mcpQ} onChange={(e) => setMcpQ(e.target.value)} placeholder="搜索 MCP，如 github" />
          <button className="btn btn-primary" type="submit" disabled={busy}>
            搜索 Hub
          </button>
        </form>
        <ul className="settings-list">
          {mcpHits.map((item) => (
            <li key={item.name}>
              <span>
                <strong>{item.title || item.name}</strong>
                <span className="muted">
                  {" "}
                  · {item.transport}
                  {item.command ? ` · ${item.command} ${item.args || ""}` : ""}
                  {item.url ? ` · ${item.url}` : ""}
                </span>
                <div className="muted">{item.description}</div>
              </span>
              <button
                type="button"
                className="btn btn-primary"
                disabled={busy}
                onClick={() =>
                  void (async () => {
                    setBusy(true);
                    try {
                      setData(await installMcpFromHub(item));
                      setStatus(`已安装 MCP：${item.title || item.name}`);
                    } catch (err) {
                      setStatus(err instanceof Error ? err.message : String(err));
                    } finally {
                      setBusy(false);
                    }
                  })()
                }
              >
                安装
              </button>
            </li>
          ))}
        </ul>
        <h3 className="settings-subhead">已安装</h3>
        <ul className="settings-list">
          {mcp.length === 0 ? (
            <li className="muted">暂无</li>
          ) : (
            mcp.map((m: McpServerItem) => (
              <li key={m.id || m.name}>
                <label className="settings-check">
                  <input
                    type="checkbox"
                    checked={!!m.enabled}
                    disabled={busy}
                    onChange={(e) => {
                      const next = mcp.map((x) =>
                        (x.id || x.name) === (m.id || m.name) ? { ...x, enabled: e.target.checked } : x,
                      );
                      void persist({ mcp_servers: next });
                    }}
                  />
                  <span>
                    <strong>{m.name}</strong>
                    <span className="muted">
                      {" "}
                      · {m.transport}
                      {m.command ? ` · ${m.command}` : ""}
                      {m.args ? ` ${m.args}` : ""}
                    </span>
                  </span>
                </label>
                <button
                  type="button"
                  className="ghost compact"
                  disabled={busy}
                  onClick={() =>
                    void persist({
                      mcp_servers: mcp.filter((x) => (x.id || x.name) !== (m.id || m.name)),
                    })
                  }
                >
                  删除
                </button>
              </li>
            ))
          )}
        </ul>
      </section>

      <section className="panel settings-panel-block">
        <div className="panel-head">
          <h2>Skill Hub</h2>
        </div>
        <p className="hint">对接 skills.sh / Anthropic skills 公开目录；安装写入 `.agents/skills/`。</p>
        <form className="settings-add-grid" onSubmit={onSearchSkills}>
          <input value={skillQ} onChange={(e) => setSkillQ(e.target.value)} placeholder="搜索 Skill，如 pdf" />
          <button className="btn btn-primary" type="submit" disabled={busy}>
            搜索 Hub
          </button>
        </form>
        <ul className="settings-list">
          {skillHits.map((item) => (
            <li key={item.id}>
              <span>
                <strong>{item.name}</strong>
                <div className="muted">{item.description}</div>
              </span>
              <button
                type="button"
                className="btn btn-primary"
                disabled={busy}
                onClick={() =>
                  void (async () => {
                    setBusy(true);
                    try {
                      setData(await installSkillFromHub(item));
                      setStatus(`已安装 Skill：${item.name}`);
                    } catch (err) {
                      setStatus(err instanceof Error ? err.message : String(err));
                    } finally {
                      setBusy(false);
                    }
                  })()
                }
              >
                安装
              </button>
            </li>
          ))}
        </ul>
        <h3 className="settings-subhead">已安装</h3>
        <ul className="settings-list">
          {skills.length === 0 ? (
            <li className="muted">暂无</li>
          ) : (
            skills.map((s: SkillItem) => (
              <li key={s.id || s.name}>
                <label className="settings-check">
                  <input
                    type="checkbox"
                    checked={!!s.enabled}
                    disabled={busy}
                    onChange={(e) => {
                      const next = skills.map((x) =>
                        (x.id || x.name) === (s.id || s.name) ? { ...x, enabled: e.target.checked } : x,
                      );
                      void persist({ skills: next });
                    }}
                  />
                  <span>
                    <strong>{s.name}</strong>
                    {s.path ? <span className="muted"> — {s.path}</span> : null}
                  </span>
                </label>
                <button
                  type="button"
                  className="ghost compact"
                  disabled={busy}
                  onClick={() =>
                    void persist({
                      skills: skills.filter((x) => (x.id || x.name) !== (s.id || s.name)),
                    })
                  }
                >
                  删除
                </button>
              </li>
            ))
          )}
        </ul>
        <p className="status-line">
          {hubNote}
          {hubNote && status ? " · " : ""}
          {status}
        </p>
      </section>
    </div>
  );
}
