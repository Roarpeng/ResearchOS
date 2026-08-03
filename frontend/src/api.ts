const envBase = import.meta.env.VITE_GATEWAY_URL as string | undefined;

/** Gateway base URL. Dev proxy uses relative `/api` when unset. */
export const GATEWAY_BASE =
  envBase?.replace(/\/$/, "") ||
  (import.meta.env.DEV ? "" : "http://localhost:8000");

export type TaskCreateResponse = {
  ok?: boolean;
  data?: {
    id?: string;
    status?: string;
    plan?: unknown;
    evidence?: unknown[];
    result?: string | null;
  };
  id?: string;
  status?: string;
  plan?: unknown;
  evidence?: unknown[];
  result?: string | null;
  detail?: string;
};

export async function createResearchTask(query: string, mode: string) {
  const res = await fetch(`${GATEWAY_BASE}/api/v1/research/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({
      query,
      mode,
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

export function unwrapTask(body: TaskCreateResponse) {
  const data = body.data ?? body;
  return {
    id: data.id ?? body.id,
    status: data.status ?? body.status,
    plan: data.plan ?? body.plan,
    evidence: data.evidence ?? body.evidence,
    result: data.result ?? body.result,
  };
}
