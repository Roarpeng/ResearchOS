import { useEffect, useState, type FormEvent } from "react";
import {
  fetchLlmSettings,
  testLlmSlot,
  updateLlmSettings,
  type LlmSettings,
  type LlmSlotStatus,
} from "./api";

type SlotKind = "chat" | "embed" | "rerank";

const AGENT_ROLES: Array<{
  key: keyof LlmSettings["agents"];
  label: string;
  pool: SlotKind;
}> = [
  { key: "research", label: "Research", pool: "chat" },
  { key: "planner", label: "Planner", pool: "chat" },
  { key: "researcher", label: "Researcher", pool: "chat" },
  { key: "writer", label: "Writer", pool: "chat" },
  { key: "plc", label: "PLC", pool: "chat" },
  { key: "embed", label: "Embed", pool: "embed" },
  { key: "rerank", label: "Rerank", pool: "rerank" },
];

const TYPE_GROUPS: Array<{ kind: SlotKind; title: string; hint: string }> = [
  { kind: "chat", title: "对话模型", hint: "Chat" },
  { kind: "embed", title: "向量模型", hint: "Embedding" },
  { kind: "rerank", title: "召回模型", hint: "Rerank" },
];

const MAX_PER_KIND = 3;

type SlotDraft = { api_key: string; model: string; base_url: string };

function slotsOfKind(slots: LlmSlotStatus[], kind: SlotKind): LlmSlotStatus[] {
  return slots.filter((s) => (s.kind || "chat") === kind);
}

function draftsFromSlots(slots: LlmSlotStatus[]): Record<string, SlotDraft> {
  const out: Record<string, SlotDraft> = {};
  for (const s of slots) {
    out[s.id] = {
      api_key: "",
      model: s.model || "",
      base_url: s.base_url || "",
    };
  }
  return out;
}

function slotUpdateBody(d: SlotDraft): { api_key?: string; model?: string; base_url?: string } {
  return {
    model: d.model,
    base_url: d.base_url,
    ...(d.api_key.trim() ? { api_key: d.api_key.trim() } : {}),
  };
}

function SlotCard({
  slot,
  draft,
  busy,
  testing,
  note,
  onPatch,
  onTest,
  onRemove,
}: {
  slot: LlmSlotStatus;
  draft: SlotDraft;
  busy: boolean;
  testing: boolean;
  note?: string;
  onPatch: (patch: Partial<SlotDraft>) => void;
  onTest: () => void;
  onRemove?: () => void;
}) {
  return (
    <div className="provider-card">
      <div className="provider-card-head">
        <strong>{slot.label}</strong>
        <span className={`llm-slot-flag${slot.configured ? " on" : ""}`}>
          {slot.configured ? "已配置" : "未配置"}
        </span>
      </div>
      <div className="field">
        <label htmlFor={`base-${slot.id}`}>Base URL</label>
        <input
          id={`base-${slot.id}`}
          type="url"
          placeholder={slot.default_base_url || "https://…"}
          value={draft.base_url}
          onChange={(e) => onPatch({ base_url: e.target.value })}
        />
      </div>
      <div className="field">
        <label htmlFor={`model-${slot.id}`}>模型名称</label>
        <input
          id={`model-${slot.id}`}
          type="text"
          placeholder={slot.default_model || "model name"}
          value={draft.model}
          onChange={(e) => onPatch({ model: e.target.value })}
        />
      </div>
      <div className="field">
        <label htmlFor={`key-${slot.id}`}>API Key</label>
        <input
          id={`key-${slot.id}`}
          type="password"
          autoComplete="off"
          placeholder={slot.hint ? `已有 ${slot.hint}，留空保留` : "自定义填写"}
          value={draft.api_key}
          onChange={(e) => onPatch({ api_key: e.target.value })}
        />
      </div>
      <div className="actions">
        <button className="btn btn-ghost" type="button" disabled={busy || testing} onClick={onTest}>
          {testing ? "测试中…" : "联通测试"}
        </button>
        {onRemove ? (
          <button className="btn btn-ghost" type="button" disabled={busy || testing} onClick={onRemove}>
            删除
          </button>
        ) : null}
      </div>
      {note ? <p className="status-line llm-test-note">{note}</p> : null}
    </div>
  );
}

export default function LlmSettingsPanel() {
  const [settings, setSettings] = useState<LlmSettings | null>(null);
  const [agents, setAgents] = useState<LlmSettings["agents"] | null>(null);
  const [drafts, setDrafts] = useState<Record<string, SlotDraft>>({});
  const [busy, setBusy] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [status, setStatus] = useState("加载中…");
  const [testNotes, setTestNotes] = useState<Record<string, string>>({});

  function applyLoaded(data: LlmSettings) {
    const nextSlots = data.slots || data.providers || [];
    setSettings(data);
    setAgents(data.agents);
    setDrafts((prev) => {
      const next = draftsFromSlots(nextSlots);
      for (const [id, d] of Object.entries(next)) {
        const old = prev[id];
        if (old && (old.api_key || old.model || old.base_url) && !d.model && !d.base_url) {
          next[id] = { ...d, model: old.model || d.model, base_url: old.base_url || d.base_url, api_key: old.api_key };
        }
      }
      return next;
    });
  }

  async function load() {
    setBusy(true);
    try {
      const data = await fetchLlmSettings();
      const nextSlots = data.slots || data.providers || [];
      setSettings(data);
      setAgents(data.agents);
      setDrafts(draftsFromSlots(nextSlots));
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
        slots[id] = slotUpdateBody(d);
      }
      const data = await updateLlmSettings({ agents, slots });
      applyLoaded(data);
      setStatus("已保存。联通测试可直接点槽位按钮（不必等 LiteLLM）。");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onAdd(kind: SlotKind) {
    setBusy(true);
    try {
      const data = await updateLlmSettings({ add_slot: kind });
      applyLoaded(data);
      const added = slotsOfKind(data.slots || data.providers || [], kind);
      setStatus(`已添加${TYPE_GROUPS.find((g) => g.kind === kind)?.title}（当前 ${added.length} 个）`);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onRemove(id: string) {
    setBusy(true);
    try {
      const data = await updateLlmSettings({ remove_slot: id });
      applyLoaded(data);
      setTestNotes((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      setStatus("已删除该模型");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onTestSlot(id: string) {
    const d = drafts[id] || { api_key: "", model: "", base_url: "" };
    setTestingId(id);
    setTestNotes((prev) => ({ ...prev, [id]: "测试中…" }));
    try {
      const result = await testLlmSlot({
        slot_id: id,
        ...(d.api_key.trim() ? { api_key: d.api_key.trim() } : {}),
        model: d.model || undefined,
        base_url: d.base_url || undefined,
      });
      if (result.ok) {
        try {
          const data = await updateLlmSettings({ slots: { [id]: slotUpdateBody(d) } });
          applyLoaded(data);
          setTestNotes((prev) => ({ ...prev, [id]: `✓ ${result.message}（已保存）` }));
          setStatus(`${id} 联通成功，已保存该槽位`);
        } catch (saveErr) {
          const saveMsg = saveErr instanceof Error ? saveErr.message : String(saveErr);
          setTestNotes((prev) => ({ ...prev, [id]: `✓ ${result.message}（保存失败：${saveMsg}）` }));
          setStatus(`${id} 联通成功，但保存失败，请点「保存」`);
        }
      } else {
        setTestNotes((prev) => ({
          ...prev,
          [id]: `✗ ${result.message}${result.detail ? ` — ${result.detail}` : ""}`,
        }));
        setStatus(`${id} 联通失败`);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setTestNotes((prev) => ({ ...prev, [id]: `✗ ${msg}` }));
      setStatus(msg);
    } finally {
      setTestingId(null);
    }
  }

  const slots = settings?.slots || settings?.providers || [];
  const optionsByKind: Record<SlotKind, LlmSlotStatus[]> = {
    chat: slotsOfKind(slots, "chat"),
    embed: slotsOfKind(slots, "embed"),
    rerank: slotsOfKind(slots, "rerank"),
  };

  return (
    <div className="settings-section single">
      <form className="panel settings-panel-block" onSubmit={onSave}>
        <div className="panel-head">
          <h2>模型</h2>
        </div>
        <p className="hint">每类默认 1 个。需要更多时点「添加」，填自己的 Base URL / 模型 / Key。</p>
        {TYPE_GROUPS.map((group) => {
          const visible = optionsByKind[group.kind];
          const canAdd = visible.length < MAX_PER_KIND;
          return (
            <div className="llm-type-group" key={group.kind}>
              <div className="llm-type-group-head">
                <h3>
                  {group.title}
                  <span className="muted"> · {group.hint}</span>
                </h3>
                <button
                  className="btn btn-ghost"
                  type="button"
                  disabled={busy || !canAdd}
                  title={canAdd ? `添加一个${group.title}` : `已达上限（最多 ${MAX_PER_KIND} 个）`}
                  onClick={() => void onAdd(group.kind)}
                >
                  添加
                </button>
              </div>
              {visible.map((s) => {
                const d = drafts[s.id] || {
                  api_key: "",
                  model: s.model || "",
                  base_url: s.base_url || "",
                };
                return (
                  <SlotCard
                    key={s.id}
                    slot={s}
                    draft={d}
                    busy={busy}
                    testing={testingId === s.id}
                    note={testNotes[s.id]}
                    onPatch={(patch) => patchDraft(s.id, patch)}
                    onTest={() => void onTestSlot(s.id)}
                    onRemove={s.removable ? () => void onRemove(s.id) : undefined}
                  />
                );
              })}
            </div>
          );
        })}

        <details className="settings-fold">
          <summary>Agent 绑定</summary>
          <p className="hint">把角色指到上面已添加的模型。</p>
          {agents &&
            AGENT_ROLES.map((role) => {
              const options = optionsByKind[role.pool];
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
        </details>

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
    </div>
  );
}
