const envBase = import.meta.env.VITE_GATEWAY_URL as string | undefined;

/** Gateway base URL. Dev proxy uses relative `/api` when unset. */
export const GATEWAY_BASE =
  envBase?.replace(/\/$/, "") ||
  (import.meta.env.DEV ? "" : "http://localhost:8000");

export const WS_BASE = GATEWAY_BASE
  ? GATEWAY_BASE.replace(/^http/, "ws")
  : (import.meta.env.DEV ? "ws://localhost:8000" : "ws://localhost:8000");

export type TaskCreateResponse = {
  ok?: boolean;
  data?: {
    id?: string;
    status?: string;
    plan?: unknown;
    evidence?: unknown[];
    result?: string | null;
    citations?: unknown[];
    events?: unknown[];
    interrupts?: unknown[];
  };
  id?: string;
  status?: string;
  plan?: unknown;
  evidence?: unknown[];
  result?: string | null;
  citations?: unknown[];
  events?: unknown[];
  interrupts?: unknown[];
  detail?: string;
};

export async function createResearchTask(
  query: string,
  mode: string,
  options?: { tiaExportDir?: string },
) {
  const res = await fetch(`${GATEWAY_BASE}/api/v1/research/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({
      query,
      mode,
      ...(options?.tiaExportDir?.trim()
        ? { tia_export_dir: options.tiaExportDir.trim() }
        : {}),
      options: {
        language: "zh-CN",
        enable_web: true,
        citation_required: true,
        report_format: ["markdown"],
      },
    }),
  });
  const text = await res.text();
  let body: TaskCreateResponse = {};
  try {
    body = text ? (JSON.parse(text) as TaskCreateResponse) : {};
  } catch {
    body = { detail: text || res.statusText };
  }
  if (!res.ok) {
    throw new Error(body.detail || `Gateway ${res.status}`);
  }
  return body;
}

export async function fetchTask(taskId: string) {
  const res = await fetch(`${GATEWAY_BASE}/api/v1/research/tasks/${taskId}`, {
    headers: { Accept: "application/json" },
  });
  const text = await res.text();
  let body: TaskCreateResponse = {};
  try {
    body = text ? (JSON.parse(text) as TaskCreateResponse) : {};
  } catch {
    body = { detail: text || res.statusText };
  }
  if (!res.ok) {
    throw new Error(body.detail || `Gateway ${res.status}`);
  }
  return body;
}

export async function resumeTask(
  taskId: string,
  resolution: string = "approve",
  interruptId?: string,
) {
  const res = await fetch(
    `${GATEWAY_BASE}/api/v1/research/tasks/${taskId}/resume`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ resolution, interrupt_id: interruptId }),
    },
  );
  const text = await res.text();
  let body: TaskCreateResponse = {};
  try {
    body = text ? (JSON.parse(text) as TaskCreateResponse) : {};
  } catch {
    body = { detail: text || res.statusText };
  }
  if (!res.ok) {
    throw new Error(body.detail || `Gateway ${res.status}`);
  }
  return body;
}

export async function cancelTask(taskId: string) {
  const res = await fetch(
    `${GATEWAY_BASE}/api/v1/research/tasks/${taskId}/cancel`,
    {
      method: "POST",
      headers: { Accept: "application/json" },
    },
  );
  const text = await res.text();
  let body: TaskCreateResponse = {};
  try {
    body = text ? (JSON.parse(text) as TaskCreateResponse) : {};
  } catch {
    body = { detail: text || res.statusText };
  }
  if (!res.ok) {
    throw new Error(body.detail || `Gateway ${res.status}`);
  }
  return body;
}

export function unwrapTask(body: TaskCreateResponse) {
  const data = body.data ?? body;
  return {
    id: data.id ?? body.id,
    status: data.status ?? body.status,
    plan: data.plan ?? body.plan,
    evidence: data.evidence ?? body.evidence,
    result: data.result ?? body.result,
    citations: data.citations ?? body.citations,
    events: data.events ?? body.events,
    interrupts: data.interrupts ?? body.interrupts,
  };
}

/** Create a WebSocket connection to the research stream. */
export function connectResearchStream(
  taskId: string,
  onEvent: (event: Record<string, unknown>) => void,
  onError?: (err: Event) => void,
): WebSocket {
  const ws = new WebSocket(`${WS_BASE}/api/v1/ws/research/${taskId}`);
  ws.onopen = () => {
    ws.send(JSON.stringify({ type: "auth", token: "dev", last_seq: 0 }));
  };
  ws.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data as string);
      onEvent(data);
    } catch {
      // ignore parse errors
    }
  };
  ws.onerror = (err) => {
    onError?.(err);
  };
  return ws;
}
