/**
 * Research-console data models.
 *
 * Pure helpers that normalize REST task snapshots and WebSocket event
 * envelopes into the shapes consumed by Timeline / CitationRail / the HITL
 * interrupt bar. No backend changes required — everything reads fields the
 * gateway/runtime already expose.
 */

export type ResearchEvent = {
  type: string;
  ts: string;
  seq?: number;
  payload: Record<string, unknown>;
  summary: string;
};

export type CitationItem = {
  id: string;
  title: string;
  url: string;
  locator: string;
  quote: string;
  source: string;
};

export type InterruptItem = {
  id: string;
  prompt: string;
  options: string[];
  kind: string;
  resolved: boolean;
};

function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" ? (v as Record<string, unknown>) : {};
}

function asArray(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

function firstString(...vals: unknown[]): string {
  for (const v of vals) {
    if (typeof v === "string") {
      const t = v.trim();
      if (t) return t;
    } else if (typeof v === "number") {
      return String(v);
    }
  }
  return "";
}

/** Summarize an event payload into one compact, human-readable line. */
export function summarizePayload(payload: unknown): string {
  const p = asRecord(payload);
  if (!Object.keys(p).length) return "";
  const preferred = [
    "tool",
    "agent",
    "title",
    "step",
    "status",
    "result_summary",
    "summary",
    "prompt",
    "resolution",
    "name",
    "kind",
  ];
  const bits: string[] = [];
  for (const key of preferred) {
    const v = p[key];
    if (typeof v === "string" && v.trim()) bits.push(v.trim());
    else if (typeof v === "number" || typeof v === "boolean") {
      bits.push(`${key}=${String(v)}`);
    }
  }
  if (bits.length) return bits.slice(0, 3).join(" · ");
  for (const v of Object.values(p)) {
    if (typeof v === "string" && v.trim() && v.length <= 200) return v.trim();
  }
  try {
    return JSON.stringify(p).slice(0, 180);
  } catch {
    return "";
  }
}

/** Normalize a REST runtime event or a WS envelope into a ResearchEvent. */
export function normalizeEvent(raw: unknown): ResearchEvent | null {
  const r = asRecord(raw);
  const type = firstString(r.event_type, r.type);
  if (!type) return null;
  const payload = asRecord(r.payload);
  return {
    type,
    ts: firstString(r.ts, r.created_at, r.time),
    seq: typeof r.seq === "number" ? r.seq : undefined,
    payload,
    summary: summarizePayload(payload),
  };
}

/** Normalize a list of events (REST array or `{ events: [...] }` wrapper). */
export function normalizeEvents(raw: unknown): ResearchEvent[] {
  const list = Array.isArray(raw) ? raw : asRecord(raw).events;
  return asArray(list)
    .map(normalizeEvent)
    .filter((e): e is ResearchEvent => e !== null);
}

export function normalizeCitation(raw: unknown, index: number): CitationItem | null {
  const c = asRecord(raw);
  const id = firstString(c.id, c.citation_id, c.source_id, c.evidence_id) || `cit-${index}`;
  const title = firstString(c.title, c.name);
  const url = firstString(c.url, c.link);
  const locator = firstString(c.locator, c.chunk_id, c.block, c.network);
  const quote = firstString(c.quote, c.snippet, c.evidence, c.content);
  const source = firstString(c.source_id, c.evidence_id, c.publisher, c.source_type, c.source);
  if (!title && !url && !locator && !quote && !source) return null;
  return { id, title, url, locator, quote, source };
}

function dedupCitations(items: CitationItem[]): CitationItem[] {
  const seen = new Set<string>();
  const out: CitationItem[] = [];
  for (const c of items) {
    if (seen.has(c.id)) continue;
    seen.add(c.id);
    out.push(c);
  }
  return out;
}

export function normalizeCitations(raw: unknown): CitationItem[] {
  const list = Array.isArray(raw) ? raw : asRecord(raw).citations;
  const out: CitationItem[] = [];
  asArray(list).forEach((c, i) => {
    const n = normalizeCitation(c, i + 1);
    if (n) out.push(n);
  });
  return dedupCitations(out);
}

/**
 * Parse the writer report's footnote definitions (`[^C1]: title, url`) into
 * citations. The runtime summary does not expose the citations[] list, but the
 * report Markdown contains title/url for every stable C# id.
 */
export function parseReportCitations(markdown: unknown): CitationItem[] {
  if (typeof markdown !== "string") return [];
  const out: CitationItem[] = [];
  let current: CitationItem | null = null;
  for (const raw of markdown.split(/\r?\n/)) {
    const def = raw.match(/^\[\^([^\]]+)\]:\s*(.*)$/);
    if (def) {
      if (current) out.push(current);
      const id = def[1].trim();
      const rest = def[2].trim();
      const urlMatch = rest.match(/(https?:\/\/\S+)/);
      let url = "";
      let title = rest;
      if (urlMatch) {
        url = urlMatch[1];
        title = rest
          .replace(urlMatch[0], "")
          .replace(/[,\s]+$/, "")
          .replace(/,$/, "")
          .trim();
      } else {
        const parts = rest.split(",");
        if (parts.length > 1) {
          url = parts[parts.length - 1].trim();
          title = parts.slice(0, -1).join(",").trim();
        }
      }
      current = { id, title, url, locator: "", quote: "", source: "" };
      continue;
    }
    const quote = raw.match(/^\s*Quote:\s*(.*)$/);
    if (quote && current) current.quote = quote[1].trim();
  }
  if (current) out.push(current);
  return dedupCitations(out);
}

export function normalizeInterrupts(raw: unknown): InterruptItem[] {
  return asArray(raw)
    .map((r) => {
      const it = asRecord(r);
      const inner = asRecord(it.value);
      const src = Object.keys(inner).length ? inner : it;
      const options = asArray(src.options)
        .map((o) => {
          if (typeof o === "string") return o;
          const rec = asRecord(o);
          return firstString(rec.label, rec.value, rec.id, rec.action, rec.text);
        })
        .filter(Boolean);
      return {
        id: firstString(src.interrupt_id, src.id),
        prompt: firstString(src.prompt, src.message),
        options,
        kind: firstString(src.kind, src.interrupt_type),
        resolved: Boolean(src.resolved) || Boolean(src.resolution),
      };
    })
    .filter((it) => it.prompt || it.id || it.options.length);
}

/** Extract the runtime snapshot nested under task.result.runtime. */
export function taskRuntime(task: unknown): Record<string, unknown> {
  return asRecord(asRecord(asRecord(task).result).runtime);
}

/** Collect the ordered, unresolved HITL interrupts for a task snapshot. */
export function collectInterrupts(task: unknown): InterruptItem[] {
  const t = asRecord(task);
  const runtime = taskRuntime(t);
  const sources: unknown[] = [t.interrupts, runtime.pending_interrupts, runtime.interrupts];
  const seen = new Set<string>();
  const out: InterruptItem[] = [];
  for (const src of sources) {
    for (const it of normalizeInterrupts(src)) {
      if (it.resolved) continue;
      const key = it.id || `${it.prompt}|${it.options.join(",")}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(it);
    }
  }
  return out;
}

/** Collect citations from task.citations, runtime evidence and the report body. */
export function collectCitations(task: unknown): CitationItem[] {
  const t = asRecord(task);
  const runtime = taskRuntime(t);
  const merged: unknown[] = [
    ...asArray(t.citations),
    ...asArray(runtime.citations),
    ...asArray(runtime.evidence),
  ];
  return dedupCitations([...normalizeCitations(merged), ...parseReportCitations(runtime.result)]);
}

/** Collect the event stream for a task snapshot (runtime events). */
export function collectEvents(task: unknown): ResearchEvent[] {
  return normalizeEvents(taskRuntime(task).events);
}
