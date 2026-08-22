import type { PlcCoverage, PlcJobDetail } from "../api";

function coverageConvertedPct(cov: PlcCoverage | null | undefined): number {
  const total = Number(cov?.total_blocks || 0);
  const converted = Number(cov?.converted || 0);
  if (!total) return 0;
  return Math.max(0, Math.min(100, Math.round((converted / total) * 100)));
}

function topTodoParts(cov: PlcCoverage | null | undefined, limit = 4): Array<{ name: string; count: number }> {
  const top = cov?.top_untranslated_parts || [];
  if (top.length) {
    return top
      .map((r) => ({ name: String(r.name || ""), count: Number(r.count || 0) }))
      .filter((r) => r.name)
      .slice(0, limit);
  }
  return Object.entries(cov?.todo_histogram || {})
    .map(([name, count]) => ({ name, count: Number(count) }))
    .sort((a, b) => b.count - a.count)
    .slice(0, limit);
}

function obCallTree(detail: PlcJobDetail | null): string[] {
  const nodes = detail?.logic_graph?.nodes || [];
  const edges = (detail?.logic_graph?.edges || []).filter((e) => String(e.type || "") === "CALLS");
  if (!edges.length) return [];
  const labelOf = (id: string) => {
    const n = nodes.find((x) => String(x.id || "") === id);
    const props = (n?.props || {}) as Record<string, unknown>;
    const raw = String(n?.label || props.name || id);
    return raw.includes("::") ? raw.split("::").pop() || raw : raw;
  };
  const obs = nodes.filter((n) => {
    const props = (n.props || {}) as Record<string, unknown>;
    const t = String(n.type || props.block_type || "").toUpperCase();
    const name = String(props.name || n.label || "");
    return t === "OB" || /^ob\d+/i.test(name) || name === "Main";
  });
  const roots = obs.length ? obs : nodes.slice(0, 1);
  const lines: string[] = [];
  for (const ob of roots.slice(0, 2)) {
    const oid = String(ob.id || "");
    const kids = edges
      .filter((e) => String(e.source || "") === oid)
      .map((e) => labelOf(String(e.target || "")))
      .filter(Boolean);
    if (!kids.length) continue;
    lines.push(`${labelOf(oid)} → ${kids.slice(0, 8).join(" → ")}`);
  }
  return lines.slice(0, 3);
}

export function PlcCoverageStrip({ detail }: { detail: PlcJobDetail | null }) {
  const cov = detail?.coverage;
  if (!cov || !Number(cov.total_blocks || 0)) return null;
  const pct = coverageConvertedPct(cov);
  const r = 16;
  const c = 2 * Math.PI * r;
  const dash = (pct / 100) * c;
  const todos = topTodoParts(cov);
  const tree = obCallTree(detail);
  const rate = Number(cov.todo_rate || 0);
  const skipChips: string[] = [];
  const seenSkip = new Set<string>();
  for (const [cat, row] of Object.entries(cov.categories || {})) {
    for (const skip of row.skipped_reasons || []) {
      const reason = String(skip.reason || "").trim();
      if (!reason) continue;
      const key = `${cat}:${reason}`;
      if (seenSkip.has(key)) continue;
      seenSkip.add(key);
      skipChips.push(`${cat}/${reason}`);
      if (skipChips.length >= 8) break;
    }
    if (skipChips.length >= 8) break;
  }
  return (
    <div className="plc-coverage" aria-label="转换覆盖率">
      <svg className="plc-coverage-ring" viewBox="0 0 40 40" width="40" height="40" aria-hidden="true">
        <circle cx="20" cy="20" r={r} fill="none" stroke="var(--line)" strokeWidth="4" />
        <circle
          cx="20"
          cy="20"
          r={r}
          fill="none"
          stroke="var(--accent)"
          strokeWidth="4"
          strokeDasharray={`${dash} ${c - dash}`}
          strokeLinecap="round"
          transform="rotate(-90 20 20)"
        />
        <text x="20" y="22" textAnchor="middle" fontSize="9" fill="currentColor">
          {pct}%
        </text>
      </svg>
      <div className="plc-coverage-meta">
        <div>
          已转换 {cov.converted ?? 0}/{cov.total_blocks ?? 0} · TODO {rate.toLocaleString(undefined, { style: "percent", maximumFractionDigits: 1 })}
          {cov.safety_block_count ? ` · F-block ${cov.safety_block_count}` : ""}
        </div>
        {todos.length ? (
          <div className="plc-coverage-todos">
            未译 Part：
            {todos.map((t) => (
              <span key={t.name} className="plc-chip">
                {t.name} × {t.count}
              </span>
            ))}
          </div>
        ) : (
          <div className="muted">无未译 Part</div>
        )}
        {tree.length ? <div className="plc-coverage-tree">OB 调用：{tree.join("；")}</div> : null}
        {skipChips.length ? (
          <div className="plc-coverage-todos">
            Openness 跳过：
            {skipChips.map((s) => (
              <span key={s} className="plc-chip">
                {s}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
