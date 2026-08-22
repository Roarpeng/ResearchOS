import type { CitationItem, InterruptItem, ResearchEvent } from "../researchModel";

export function mergeEvents(prev: ResearchEvent[], next: ResearchEvent[]): ResearchEvent[] {
  const seen = new Set(prev.map((e) => `${e.seq ?? "s"}|${e.type}|${e.ts}`));
  const out = [...prev];
  for (const e of next) {
    const key = `${e.seq ?? "s"}|${e.type}|${e.ts}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(e);
  }
  return out;
}

export function mergeInterrupts(prev: InterruptItem[], next: InterruptItem[]): InterruptItem[] {
  const seen = new Set(prev.map((i) => i.id || `${i.prompt}|${i.options.join(",")}`));
  const out = [...prev];
  for (const it of next) {
    const key = it.id || `${it.prompt}|${it.options.join(",")}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(it);
  }
  return out;
}

export function mergeCitations(prev: CitationItem[], next: CitationItem[]): CitationItem[] {
  const seen = new Set(prev.map((c) => c.id));
  const out = [...prev];
  for (const c of next) {
    if (seen.has(c.id)) continue;
    seen.add(c.id);
    out.push(c);
  }
  return out;
}
