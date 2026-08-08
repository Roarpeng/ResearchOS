import { useEffect, useState, type FormEvent } from "react";
import {
  fetchLlmSettings,
  updateLlmSettings,
  type LlmSettings,
  type LlmSlotStatus,
} from "./api";

const AGENT_ROLES: Array<{
  key: keyof LlmSettings["agents"];
  label: string;
  pool: "chat" | "embed" | "rerank";
}> = [
  { key: "research", label: "Research", pool: "chat" },
  { key: "planner", label: "Planner", pool: "chat" },
  { key: "researcher", label: "Researcher", pool: "chat" },
  { key: "writer", label: "Writer", pool: "chat" },
  { key: "plc", label: "PLC", pool: "chat" },
  { key: "embed", label: "Embed", pool: "embed" },
  { key: "rerank", label: "Rerank", pool: "rerank" },
];

type SlotDraft = { api_key: string; model: string; base_url: string };

function draftsFromSlots(slots: LlmSlotStatus[]): Record<string, SlotDraft> {
  const out: Record<string, SlotDraft> = {};
  for (const s of slots) {
    out[s.id] = {
      api_key: "",
      model: s.model || s.default_model || "",
      base_url: s.base_url || s.default_base_url || "",
    };
  }
  return out;
}

export default function LlmSettingsPanel() {
  const [settings, setSettings] = useState<LlmSettings | null>(null);
  const [agents, setAgents] = useState<LlmSettings["agents"] | null>(null);
  const [drafts, setDrafts] = useState<Record<string, SlotDraft>>({});
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("加载中…");

  async function load() {
    setBusy(true);
    try {
      const data = await fetchLlmSettings();
      setSettings(data);
      setAgents(data.agents);
      setDrafts(draftsFromSlots(data.slots || data.providers || []));
      setStatus("已加载");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  function patchDraft(id: string, patch: Partial<SlotDraft>) {
    setDrafts((prev) => ({
      ...prev,
      [id]: { ...(prev[id] || { api_key: "", model: "", base_url: "" }), ...patch },
    }));
  }

  async function onSave(e: FormEvent) {
    e.preventDefault();
    if (!agents) return;
    setBusy(true);
    try {
      const slots: Record<string, { api_key?: string; model?: string; base_url?: string }> = {};
      for (const [id, d] of Object.entries(drafts)) {
        slots[id] = {
          model: d.model,
          base_url: d.base_url,
          ...(d.api_key.trim() ? { api_key: d.api_key.trim() } : {}),
        };
      }
      const data = await updateLlmSettings({ agents, slots });
      setSettings(data);
      setAgents(data.agents);
      setDrafts(draftsFromSlots(data.slots || data.providers || []));
      setStatus("已保存。请重启 LiteLLM。");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const slots = settings?.slots || settings?.providers || [];
  const chatOptions = slots.filter((s) => s.kind === "chat");
  const embedOptions = slots.filter((s) => s.kind === "embed");
  const rerankOptions = slots.filter((s) => s.kind === "rerank");

  return (
    <div className="layout">
      <form className="panel" onSubmit={onSave}>
        <div className="panel-head">
          <h2>Agent 绑定</h2>
        </div>
        <p className="hint">角色只能绑到对话 A/B/C，或 Embedding / 重排序。</p>
        {agents &&
          AGENT_ROLES.map((role) => {
            const options =
              role.pool === "chat"
                ? chatOptions
                : role.pool === "embed"
                  ? embedOptions
                  : rerankOptions;
            return (
              <div className="field" key={role.key}>
                <label htmlFor={`agent-${role.key}`}>{role.label}</label>
                <select
                  id={`agent-${role.key}`}
                  value={agents[role.key]}
                  onChange={(e) => setAgents({ ...agents, [role.key]: e.target.value })}
                >
                  {options.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>
            );
          })}
        <div className="actions">
          <button className="btn btn-primary" type="submit" disabled={busy || !agents}>
            保存
          </button>
          <button className="btn btn-ghost" type="button" disabled={busy} onClick={() => void load()}>
            刷新
          </button>
        </div>
        <p className="status-line">{status}</p>
      </form>

      <section className="panel panels-stack">
        <div className="panel-head">
          <h2>模型槽位</h2>
        </div>
        <p className="hint">3 个对话 + Embedding + 重排序。各配 Key / Model / Base URL。</p>
        {slots.map((s) => {
          const d = drafts[s.id] || {
            api_key: "",
            model: s.model || "",
            base_url: s.base_url || "",
          };
          return (
            <div className="provider-card" key={s.id}>
              <div className="provider-card-head">
                <strong>{s.label}</strong>
                <span className="muted">
                  {s.kind} · {s.configured ? "已配置" : "未配置"}
                </span>
              </div>
              <div className="field">
                <label htmlFor={`key-${s.id}`}>API Key</label>
                <input
                  id={`key-${s.id}`}
                  type="password"
                  autoComplete="off"
                  placeholder={s.hint ? `已有 ${s.hint}，留空保留` : "可选"}
                  value={d.api_key}
                  onChange={(e) => patchDraft(s.id, { api_key: e.target.value })}
                />
              </div>
              <div className="field">
                <label htmlFor={`model-${s.id}`}>Model</label>
                <input
                  id={`model-${s.id}`}
                  type="text"
                  placeholder={s.default_model || "model id"}
                  value={d.model}
                  onChange={(e) => patchDraft(s.id, { model: e.target.value })}
                />
              </div>
              <div className="field">
                <label htmlFor={`base-${s.id}`}>Base URL</label>
                <input
                  id={`base-${s.id}`}
                  type="url"
                  placeholder={s.default_base_url || "https://…"}
                  value={d.base_url}
                  onChange={(e) => patchDraft(s.id, { base_url: e.target.value })}
                />
              </div>
            </div>
          );
        })}
      </section>
    </div>
  );
}
