export const TRI_SIZES_KEY = "researchos.tri.sizes";
export const TRI_DEFAULT = { history: 220, chat: 400 };
export const HISTORY_MIN = 160;
export const HISTORY_MAX = 400;
export const HISTORY_COLLAPSED_W = 48;
export const CHAT_MIN = 280;
export const CHAT_MAX = 720;
export const CANVAS_MIN = 260;
export const PANE_STEP = 24;

export function clamp(n: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, n));
}

export function loadTriSizes(): { history: number; chat: number; historyCollapsed: boolean } {
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

export function statusTone(status: string): string {
  const s = status.toLowerCase();
  if (/(ready|done|completed|success)/.test(s)) return "ok";
  if (/(error|fail|cancelled|canceled)/.test(s)) return "bad";
  if (/(run|busy|pending|wait|progress|interrupt)/.test(s)) return "busy";
  return "idle";
}

export function formatMsgTime(at: number): string {
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

export function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  const tag = el.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  return el.isContentEditable;
}

export function titleFromQuery(q: string): string {
  const t = q.trim().replace(/\s+/g, " ");
  return t.length > 42 ? `${t.slice(0, 40)}…` : t || "未命名话题";
}
