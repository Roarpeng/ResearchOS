import { useEffect, useState, type FormEvent } from "react";
import {
  createKnowledgeSpace,
  fetchAgentWorkspace,
  fetchKnowledgeChunks,
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
  type KnowledgeChunk,
  type KnowledgeDocument,
  type KnowledgeSpace,
  type KnowledgeStats,
  type McpServerItem,
  type SkillItem,
} from "./api";
import LlmSettingsPanel from "./LlmSettingsPanel";

type TabId = "llm" | "knowledge" | "more";

const TABS: Array<{ id: TabId; label: string }> = [
  { id: "llm", label: "模型" },
  { id: "knowledge", label: "知识库" },
  { id: "more", label: "更多" },
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
        {tab === "more" ? <MoreSettingsPanel /> : null}
      </div>
    </div>
  );
}

type RecallHit = {
  citation_id: string;
  score: number;
  text: string;
  source_id: string;
  metadata?: { channels?: string[]; chunk_id?: string };
};

function KnowledgeSettingsPanel() {
  const [spaces, setSpaces] = useState<KnowledgeSpace[]>([]);
  const [activeId, setActiveId] = useState("");
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [stats, setStats] = useState<KnowledgeStats | null>(null);
  const [selectedDocId, setSelectedDocId] = useState("");
  const [chunks, setChunks] = useState<KnowledgeChunk[]>([]);
  const [chunkNote, setChunkNote] = useState("");
  const [searchQ, setSearchQ] = useState("");
  const [recallMode, setRecallMode] = useState<"vector" | "hybrid">("vector");
  const [searchHits, setSearchHits] = useState<RecallHit[]>([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");

  const docs: KnowledgeDocument[] = (() => {
    const fromSpace = spaces.find((s) => s.id === activeId)?.documents || [];
    if (fromSpace.length) return fromSpace;
    return (stats?.documents || []).map((d) => ({
      id: d.id,
      title: d.title,
      filename: d.filename,
      status: d.status,
      chunk_count: d.chunk_count,
    }));
  })();

  async function loadChunks(spaceId: string, docId: string) {
    if (!spaceId) return;
    try {
      const res = await fetchKnowledgeChunks(spaceId, docId || undefined, 80);
      setChunks(res.chunks || []);
      const withVec = (res.chunks || []).filter((c) => c.has_vector).length;
      setChunkNote(
        res.count
          ? `${res.count} 条分块${withVec ? ` · ${withVec} 条已向量化` : " · 尚无向量（检查向量模型）"}`
          : "暂无分块",
      );
    } catch (err) {
      setChunks([]);
      setChunkNote(err instanceof Error ? err.message : String(err));
    }
  }

  async function refreshStats(id: string) {
    if (!id) return;
    try {
      const s = await fetchKnowledgeStats(id);
      setStats(s);
    } catch {
      /* ignore */
    }
  }

  async function load(nextId?: string) {
    setBusy(true);
    try {
      let list = await listKnowledgeSpaces();
      if (!list.length) {
        const created = await createKnowledgeSpace("默认知识库");
        list = [created];
      }
      setSpaces(list);
      const id = nextId || activeId || list[0]?.id || "";
      setActiveId(id);
      await refreshStats(id);
      await loadChunks(id, selectedDocId);
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
    if (!activeId) return;
    void refreshStats(activeId);
    void loadChunks(activeId, selectedDocId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId, selectedDocId]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      const space = await createKnowledgeSpace(name.trim());
      setSpaces((prev) => [space, ...prev]);
      setActiveId(space.id);
      setSelectedDocId("");
      setName("");
      setCreating(false);
      setStatus(`已创建 ${space.name}`);
      await refreshStats(space.id);
      await loadChunks(space.id, "");
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
      setStatus(`已入库 ${res.title || file.name} · ${res.chunk_count} 分块`);
      setFile(null);
      setSelectedDocId(res.id);
      await load(activeId);
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
      setStatus(`索引已重建：${r.chunk_count} 分块` + (r.warnings?.length ? `（${r.warnings[0]}）` : ""));
      await refreshStats(activeId);
      await loadChunks(activeId, selectedDocId);
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
      const res = await searchKnowledge(searchQ.trim(), [activeId], 6, recallMode);
      setSearchHits(res.hits || []);
      setStatus(res.message || `${recallMode === "vector" ? "向量" : "混合"}召回 ${res.hits?.length || 0} 条`);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const active = spaces.find((s) => s.id === activeId) || spaces[0];
  const selectedChunk = chunks[0];

  return (
    <div className="settings-section kb-layout">
      <div className="panel settings-panel-block">
        <div className="kb-toolbar">
          <select
            id="kb-space"
            aria-label="知识空间"
            value={active?.id || ""}
            onChange={(e) => {
              setActiveId(e.target.value);
              setSelectedDocId("");
              setSearchHits([]);
            }}
          >
            {spaces.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          {creating ? (
            <form className="kb-create" onSubmit={onCreate}>
              <input
                autoFocus
                placeholder="新空间名称"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <button className="btn btn-primary" type="submit" disabled={busy || !name.trim()}>
                创建
              </button>
              <button className="btn btn-ghost" type="button" onClick={() => setCreating(false)}>
                取消
              </button>
            </form>
          ) : (
            <button className="btn btn-ghost" type="button" onClick={() => setCreating(true)}>
              新建
            </button>
          )}
        </div>
        {stats ? (
          <p className="hint">
            {stats.document_count} 份文本 · {stats.chunk_count} 分块
            {stats.channels?.vector ? " · 向量已就绪" : ""}
            {stats.entity_count ? ` · ${stats.entity_count} 实体` : ""}
          </p>
        ) : null}
        <form className="upload-row" onSubmit={onUpload}>
          <input
            type="file"
            accept=".pdf,.txt,.md,.docx,.doc,.csv,.json,.xml,.html"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          <button className="btn btn-primary" type="submit" disabled={busy || !file || !active}>
            上传
          </button>
          <button className="btn btn-ghost" type="button" disabled={busy || !active} onClick={() => void onRebuild()}>
            重建索引
          </button>
        </form>

        <div className="kb-split">
          <div className="kb-docs">
            <h3 className="settings-subhead">文本</h3>
            <ul className="settings-list kb-doc-list">
              <li>
                <button
                  type="button"
                  className={selectedDocId === "" ? "kb-doc on" : "kb-doc"}
                  onClick={() => setSelectedDocId("")}
                >
                  <strong>全部</strong>
                  <span className="muted">{stats?.chunk_count || 0} 分块</span>
                </button>
              </li>
              {docs.length === 0 ? (
                <li className="muted">暂无文本，上传后自动分块并向量化</li>
              ) : (
                docs.map((d) => (
                  <li key={d.id}>
                    <button
                      type="button"
                      className={selectedDocId === d.id ? "kb-doc on" : "kb-doc"}
                      onClick={() => setSelectedDocId(d.id)}
                    >
                      <strong>{d.title || d.filename || d.id}</strong>
                      <span className="muted">
                        {d.chunk_count ? `${d.chunk_count} 分块` : d.status || ""}
                      </span>
                    </button>
                  </li>
                ))
              )}
            </ul>
          </div>
          <div className="kb-chunks">
            <h3 className="settings-subhead">向量结果</h3>
            <p className="hint">{chunkNote || "点左侧文本查看分块与向量"}</p>
            <ul className="settings-list kb-chunk-list">
              {chunks.length === 0 ? (
                <li className="muted">无分块</li>
              ) : (
                chunks.map((c) => (
                  <li key={c.chunk_id} className="kb-chunk">
                    <div className="kb-chunk-meta">
                      <strong>{c.section_type || c.chunk_id.slice(0, 12)}</strong>
                      <span className={`llm-slot-flag${c.has_vector ? " on" : ""}`}>
                        {c.has_vector ? `向量 ${c.dim}d` : "无向量"}
                      </span>
                    </div>
                    {c.has_vector && c.vector_preview?.length ? (
                      <code className="kb-vector">
                        [{c.vector_preview.map((n) => n.toFixed(3)).join(", ")}
                        {(c.dim || 0) > (c.vector_preview.length || 0) ? ", …" : ""}]
                      </code>
                    ) : null}
                    <p className="kb-chunk-text">{c.text}</p>
                  </li>
                ))
              )}
            </ul>
            {selectedChunk && !selectedChunk.has_vector ? (
              <p className="hint">未向量化：到「模型」页配置向量模型并点重建索引。</p>
            ) : null}
          </div>
        </div>
      </div>

      <section className="panel settings-panel-block">
        <div className="panel-head">
          <h2>召回测试</h2>
        </div>
        <p className="hint">用当前空间测向量相似度；混合会叠加 BM25 / 图谱。</p>
        <div className="kb-mode" role="group" aria-label="召回方式">
          <button
            type="button"
            className={recallMode === "vector" ? "on" : ""}
            onClick={() => setRecallMode("vector")}
          >
            向量
          </button>
          <button
            type="button"
            className={recallMode === "hybrid" ? "on" : ""}
            onClick={() => setRecallMode("hybrid")}
          >
            混合
          </button>
        </div>
        <form className="settings-add-grid kb-recall" onSubmit={onSearch}>
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
              <li key={`${h.citation_id}-${h.score}`} className="kb-hit">
                <span>
                  <strong>{h.source_id || h.metadata?.chunk_id || "hit"}</strong>
                  <span className="muted">
                    {" "}
                    · {h.score.toFixed(3)}
                    {h.metadata?.channels?.length ? ` · ${h.metadata.channels.join("+")}` : ""}
                  </span>
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

function MoreSettingsPanel() {
  return (
    <div className="settings-section single">
      <AgentToolsPanel />
      <McpSkillPanel />
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
    <>
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
    </>
  );
}
