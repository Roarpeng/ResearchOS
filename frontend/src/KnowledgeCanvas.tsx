import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";

export type KnowledgeSource = {
  type?: string;
  role?: string;
  quote?: string;
  task_id?: string;
  turn_id?: string;
  block_name?: string;
  block_type?: string;
  project?: string;
  path?: string;
  plc_job_id?: string;
};

export type KnowledgeNode = {
  id: string;
  label: string;
  summary?: string;
  kind?: string;
  x: number;
  y: number;
  source?: KnowledgeSource;
  /** Degree-0 block/tag with no DEPENDS_ON — bottom strip, not galaxy. */
  isolate?: boolean;
};

export type KnowledgeEdge = {
  id: string;
  source: string;
  target: string;
  label?: string;
  user_created?: boolean;
};

export type KnowledgeCanvasData = {
  nodes: KnowledgeNode[];
  edges: KnowledgeEdge[];
};

export type LogicGraphData = {
  nodes: Array<{ id: string; label: string; type?: string; props?: Record<string, unknown> }>;
  edges: Array<{ source: string; target: string; type?: string; seq?: number }>;
};

export type CanvasViewMode = "knowledge" | "logic" | "both";

type Props = {
  data: KnowledgeCanvasData;
  logicGraph?: LogicGraphData | null;
  onChange: (next: KnowledgeCanvasData) => void;
  onDeepDive: (node: KnowledgeNode, question: string) => Promise<void> | void;
  /** Optional: auto-describe when a PLC block node is clicked (not dragged). */
  onNodeDescribe?: (node: KnowledgeNode) => Promise<void> | void;
  busy?: boolean;
};

const COL_W = 160;
const ROW_H = 100;
const MARGIN = 48;

function shortLabel(s: string, n = 16) {
  const t = (s || "").trim();
  return t.length > n ? `${t.slice(0, n - 1)}…` : t;
}

const KG_SPLIT_KEY = "researchos.kg.splitPct";
const KG_SPLIT_DEFAULT = 50;

function loadKgSplitPct(): number {
  try {
    const n = Number(localStorage.getItem(KG_SPLIT_KEY));
    if (!Number.isFinite(n)) return KG_SPLIT_DEFAULT;
    return Math.min(75, Math.max(25, n));
  } catch {
    return KG_SPLIT_DEFAULT;
  }
}

function normalizePad(nodes: KnowledgeNode[]): KnowledgeNode[] {
  if (!nodes.length) return nodes;
  const minX = Math.min(...nodes.map((n) => n.x));
  const minY = Math.min(...nodes.map((n) => n.y));
  const dx = minX < MARGIN ? MARGIN - minX : 0;
  const dy = minY < MARGIN ? MARGIN - minY : 0;
  if (!dx && !dy) return nodes;
  return nodes.map((n) => ({ ...n, x: n.x + dx, y: n.y + dy }));
}

/** Connected components for galaxy clustering. */
function components(
  ids: string[],
  edges: Array<{ source: string; target: string }>,
): string[][] {
  const adj = new Map<string, Set<string>>();
  ids.forEach((id) => adj.set(id, new Set()));
  edges.forEach((e) => {
    if (!adj.has(e.source) || !adj.has(e.target)) return;
    adj.get(e.source)!.add(e.target);
    adj.get(e.target)!.add(e.source);
  });
  const seen = new Set<string>();
  const out: string[][] = [];
  for (const id of ids) {
    if (seen.has(id)) continue;
    const stack = [id];
    const comp: string[] = [];
    seen.add(id);
    while (stack.length) {
      const cur = stack.pop()!;
      comp.push(cur);
      for (const nb of adj.get(cur) || []) {
        if (seen.has(nb)) continue;
        seen.add(nb);
        stack.push(nb);
      }
    }
    out.push(comp);
  }
  return out.sort((a, b) => b.length - a.length);
}

/**
 * Galaxy layout: cluster by functional dependency edges.
 * Connected components → mini-galaxies; degree-0 isolates → bottom strip
 * (not a fake second ring “galaxy”).
 */
export function autoLayoutKnowledge(
  nodes: KnowledgeNode[],
  edges: KnowledgeEdge[] = [],
): KnowledgeNode[] {
  const project = nodes.filter((n) => n.kind === "plc_project");
  const blocks = nodes.filter((n) => n.kind === "plc_block" || n.kind === "plc_tag");
  const other = nodes.filter(
    (n) => n.kind !== "plc_project" && n.kind !== "plc_block" && n.kind !== "plc_tag",
  );
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const blockIds = blocks.map((n) => n.id);
  const depEdges = edges.filter((e) => {
    const lab = e.label || "";
    return lab === "DEPENDS_ON" || lab === "INSTANCE_OF" || e.user_created;
  });

  const comps = components(
    blockIds,
    depEdges.map((e) => ({ source: e.source, target: e.target })),
  );

  const degree = new Map<string, number>();
  blockIds.forEach((id) => degree.set(id, 0));
  depEdges.forEach((e) => {
    degree.set(e.source, (degree.get(e.source) || 0) + 1);
    degree.set(e.target, (degree.get(e.target) || 0) + 1);
  });

  // Isolates (no DEPENDS_ON) are normal for pure DBs / unused blocks — not a galaxy.
  const orphans: string[] = [];
  const galaxies: string[][] = [];
  comps.forEach((comp) => {
    if (comp.length === 1 && (degree.get(comp[0]) || 0) === 0) {
      orphans.push(comp[0]);
    } else {
      galaxies.push(comp);
    }
  });

  const out: KnowledgeNode[] = [];
  const galaxyCount = Math.max(galaxies.length, 1);
  const orbitR = 220 + Math.min(galaxyCount, 6) * 50;

  galaxies.forEach((comp, gi) => {
    const angle = -Math.PI / 2 + (2 * Math.PI * gi) / galaxyCount;
    const gcx =
      520 + (galaxyCount > 1 ? orbitR * Math.cos(angle) : 0);
    const gcy =
      360 + (galaxyCount > 1 ? orbitR * Math.sin(angle) * 0.75 : 0);

    const hubId =
      [...comp].sort(
        (a, b) => (degree.get(b) || 0) - (degree.get(a) || 0) || a.localeCompare(b),
      )[0] || comp[0];

    const hop = new Map<string, number>();
    hop.set(hubId, 0);
    const q = [hubId];
    const localAdj = new Map<string, string[]>();
    comp.forEach((id) => localAdj.set(id, []));
    depEdges.forEach((e) => {
      if (comp.includes(e.source) && comp.includes(e.target)) {
        localAdj.get(e.source)!.push(e.target);
        localAdj.get(e.target)!.push(e.source);
      }
    });
    while (q.length) {
      const cur = q.shift()!;
      for (const nb of localAdj.get(cur) || []) {
        if (hop.has(nb)) continue;
        hop.set(nb, (hop.get(cur) || 0) + 1);
        q.push(nb);
      }
    }
    comp.forEach((id) => {
      if (!hop.has(id)) hop.set(id, 2);
    });

    const byRing = new Map<number, string[]>();
    hop.forEach((r, id) => {
      const list = byRing.get(r) || [];
      list.push(id);
      byRing.set(r, list);
    });

    byRing.forEach((ids, ring) => {
      const sorted = ids.slice().sort((a, b) => {
        const na = byId.get(a)?.label || a;
        const nb = byId.get(b)?.label || b;
        return na.localeCompare(nb);
      });
      if (ring === 0) {
        const n = byId.get(sorted[0]);
        if (n) out.push({ ...n, isolate: false, x: gcx, y: gcy });
        return;
      }
      const n = sorted.length;
      const radius = 85 + ring * 88 + Math.max(0, n - 8) * 5;
      sorted.forEach((id, i) => {
        const node = byId.get(id);
        if (!node) return;
        const a = -Math.PI / 2 + (2 * Math.PI * i) / n;
        out.push({
          ...node,
          isolate: false,
          x: gcx + radius * Math.cos(a),
          y: gcy + radius * Math.sin(a),
        });
      });
    });
  });

  // Orphan strip (no variable-dependency links)
  const orphanBaseY =
    (out.length ? Math.max(...out.map((n) => n.y)) : 360) + 160;
  orphans
    .slice()
    .sort((a, b) => (byId.get(a)?.label || "").localeCompare(byId.get(b)?.label || ""))
    .forEach((id, i) => {
      const node = byId.get(id);
      if (!node) return;
      const cols = Math.min(10, Math.max(4, Math.ceil(Math.sqrt(orphans.length))));
      out.push({
        ...node,
        isolate: true,
        x: MARGIN + 40 + (i % cols) * COL_W,
        y: orphanBaseY + Math.floor(i / cols) * ROW_H,
      });
    });

  project.forEach((n, i) => {
    out.push({ ...n, isolate: false, x: MARGIN + 40 + i * 160, y: MARGIN + 20 });
  });
  other.forEach((n, i) => {
    out.push({
      ...n,
      isolate: true,
      x: MARGIN + 40 + (i % 4) * COL_W,
      y: orphanBaseY + Math.ceil(orphans.length / 10) * ROW_H + 80 + Math.floor(i / 4) * ROW_H,
    });
  });

  return normalizePad(out);
}

function isObNode(n: { label: string; type?: string; props?: Record<string, unknown> }): boolean {
  const bt = String(n.props?.block_type || n.props?.type || "").toUpperCase();
  const name = n.label || "";
  return bt === "OB" || /^OB\d/i.test(name) || /^(Startup|System|Pull|Rack)/i.test(name);
}

function isMainCycleOb(n: { label: string; props?: Record<string, unknown> }): boolean {
  const name = n.label || "";
  const secondary = String(n.props?.SecondaryType || n.props?.secondary_type || "");
  if (/ProgramCycle/i.test(secondary)) return true;
  if (/OB1/i.test(name)) return true;
  if (/Main/i.test(name) && !/KuKa|Robot|Ctrl/i.test(name)) return true;
  return false;
}

/**
 * PLC scan-cycle layout (Siemens):
 * 1) Main OB (OB1) runs networks top→bottom each cycle.
 * 2) Each network Call runs that FB/FC fully, then returns — order = seq.
 * 3) Other OBs (Startup / interrupt / fault) are separate lanes, not mixed into OB1 order.
 */
function logicLayout(graph: LogicGraphData): {
  nodes: Array<{ id: string; label: string; type?: string; x: number; y: number }>;
  edges: Array<{ id: string; source: string; target: string; type: string }>;
} {
  const blockNodes = (graph.nodes || []).filter((n) => n.type === "Block");
  const byId = new Map(blockNodes.map((n) => [n.id, n]));
  const ids = new Set(blockNodes.map((n) => n.id));

  const calls = (graph.edges || []).filter(
    (e) => e.type === "CALLS" && ids.has(e.source) && ids.has(e.target),
  );
  const nexts = (graph.edges || []).filter(
    (e) => e.type === "NEXT" && ids.has(e.source) && ids.has(e.target),
  );
  const uses = (graph.edges || []).filter(
    (e) => e.type === "USES" && ids.has(e.source) && ids.has(e.target),
  );

  const callOut = new Map<string, Array<{ tgt: string; seq: number }>>();
  calls.forEach((e) => {
    const list = callOut.get(e.source) || [];
    list.push({ tgt: e.target, seq: Number(e.seq ?? 999) });
    callOut.set(e.source, list);
  });
  callOut.forEach((list, k) => {
    list.sort((a, b) => a.seq - b.seq || a.tgt.localeCompare(b.tgt));
    callOut.set(k, list);
  });

  const obs = blockNodes.filter(isObNode);
  const mainOb =
    obs.find(isMainCycleOb) ||
    [...obs].sort(
      (a, b) => (callOut.get(b.id)?.length || 0) - (callOut.get(a.id)?.length || 0),
    )[0] ||
    null;

  const STEP_X = 150;
  const LANE_Y = 170;
  const placed = new Map<string, { x: number; y: number; step?: number; lane: string }>();

  // --- Lane 0: main scan cycle ---
  if (mainOb) {
    placed.set(mainOb.id, { x: MARGIN + 40, y: MARGIN + 70, lane: "main" });
    const spine = callOut.get(mainOb.id) || [];
    const uniqueSpine: string[] = [];
    spine.forEach(({ tgt }) => {
      if (!uniqueSpine.includes(tgt)) uniqueSpine.push(tgt);
    });
    uniqueSpine.forEach((id, i) => {
      placed.set(id, {
        x: MARGIN + 220 + i * STEP_X,
        y: MARGIN + 70,
        step: i + 1,
        lane: "main",
      });
    });

    // Nested calls under each spine FB (inner networks), one row below
    uniqueSpine.forEach((parentId, pi) => {
      const nested = (callOut.get(parentId) || [])
        .map((x) => x.tgt)
        .filter((t) => t !== mainOb.id && !uniqueSpine.includes(t));
      const seen = new Set<string>();
      nested.forEach((tid, j) => {
        if (seen.has(tid) || placed.has(tid)) return;
        seen.add(tid);
        placed.set(tid, {
          x: MARGIN + 220 + pi * STEP_X + (j % 3) * 40,
          y: MARGIN + 70 + LANE_Y + Math.floor(j / 3) * 90,
          lane: "nested",
        });
      });
    });

    // DBs used by Main / spine (e.g. Main USES ceD) — place under the user
    const placeUsesFor = (userId: string, baseX: number, baseY: number) => {
      const dbs = uses.filter((e) => e.source === userId).map((e) => e.target);
      dbs.forEach((dbId, j) => {
        if (placed.has(dbId)) return;
        placed.set(dbId, {
          x: baseX + (j % 3) * 48,
          y: baseY + 110 + Math.floor(j / 3) * 80,
          lane: "uses",
        });
      });
    };
    placeUsesFor(mainOb.id, MARGIN + 40, MARGIN + 70);
    uniqueSpine.forEach((id) => {
      const pos = placed.get(id);
      if (pos) placeUsesFor(id, pos.x, pos.y);
    });
  }

  // --- Other OB lanes (startup / interrupt / fault) ---
  let lane = 1;
  obs
    .filter((o) => o.id !== mainOb?.id)
    .forEach((ob) => {
      const seq = callOut.get(ob.id) || [];
      if (!seq.length && !mainOb) {
        placed.set(ob.id, {
          x: MARGIN + 40,
          y: MARGIN + 70 + lane * (LANE_Y + 40),
          lane: "other",
        });
        lane += 1;
        return;
      }
      if (!seq.length) return; // idle fault OBs with no calls — skip clutter
      const y = MARGIN + 70 + lane * (LANE_Y + 80);
      placed.set(ob.id, { x: MARGIN + 40, y, lane: "other" });
      const uniq: string[] = [];
      seq.forEach(({ tgt }) => {
        if (!uniq.includes(tgt)) uniq.push(tgt);
      });
      uniq.forEach((id, i) => {
        if (placed.has(id)) return;
        placed.set(id, {
          x: MARGIN + 220 + i * STEP_X,
          y,
          step: i + 1,
          lane: "other",
        });
      });
      lane += 1;
    });

  // Fallback if nothing placed
  if (!placed.size) {
    blockNodes.slice(0, 20).forEach((n, i) => {
      placed.set(n.id, {
        x: MARGIN + 60 + (i % 8) * STEP_X,
        y: MARGIN + 60 + Math.floor(i / 8) * 110,
        lane: "fallback",
      });
    });
  }

  const nodes = [...placed.entries()].map(([id, pos]) => {
    const n = byId.get(id)!;
    const base = n.label || id.split("::").pop() || id;
    const label = pos.step ? `${pos.step}.${base}` : base;
    return {
      id,
      label,
      type: n.type,
      x: pos.x,
      y: pos.y,
    };
  });
  const showSet = new Set(placed.keys());

  // Edges for runtime story:
  // - NEXT along main sequence (order)
  // - CALLS from OBs into their steps (who invokes)
  // - nested CALLS under spine
  // Skip INSTANCE_OF (type link, not scan order)
  const edgeList: Array<{ id: string; source: string; target: string; type: string }> = [];
  let ei = 0;
  const addE = (source: string, target: string, type: string) => {
    if (!showSet.has(source) || !showSet.has(target) || source === target) return;
    edgeList.push({ id: `lg_${ei++}_${source}_${target}`, source, target, type });
  };

  if (mainOb) {
    const spine = (callOut.get(mainOb.id) || []).map((x) => x.tgt);
    const uniq: string[] = [];
    spine.forEach((t) => {
      if (!uniq.includes(t)) uniq.push(t);
    });
    // Prefer NEXT between consecutive steps; if missing, synthesize visual order edges
    for (let i = 0; i < uniq.length - 1; i++) {
      const hasNext = nexts.some((e) => e.source === uniq[i] && e.target === uniq[i + 1]);
      addE(uniq[i], uniq[i + 1], hasNext ? "NEXT" : "NEXT");
    }
    // OB enables the cycle — link to first step only (avoid fan-out spaghetti)
    if (uniq[0]) addE(mainOb.id, uniq[0], "CALLS");
  }

  nexts.forEach((e) => {
    if (showSet.has(e.source) && showSet.has(e.target)) {
      if (!edgeList.some((x) => x.source === e.source && x.target === e.target)) {
        addE(e.source, e.target, "NEXT");
      }
    }
  });

  // Nested CALLS (parent on spine → child)
  calls.forEach((e) => {
    if (!showSet.has(e.source) || !showSet.has(e.target)) return;
    if (mainOb && e.source === mainOb.id) return; // already linked first only
    if (isObNode(byId.get(e.source) || { label: "" })) {
      addE(e.source, e.target, "CALLS");
      return;
    }
    addE(e.source, e.target, "CALLS");
  });

  // Block → DB / instance associations (Main USES ceD, ce USES IEC_Counter_0_DB)
  uses.forEach((e) => {
    addE(e.source, e.target, "USES");
  });

  return { nodes, edges: edgeList };
}

function matchKnowledgeIds(
  knowledge: KnowledgeNode[],
  logicNodeIds: string[],
): Set<string> {
  const out = new Set<string>();
  const byBlock = new Map<string, string>();
  for (const n of knowledge) {
    const name = n.source?.block_name || n.label;
    if (name) byBlock.set(name, n.id);
    byBlock.set(n.label, n.id);
  }
  for (const lid of logicNodeIds) {
    const short = lid.includes("::") ? lid.split("::").pop() || lid : lid;
    const kid = byBlock.get(short) || byBlock.get(lid);
    if (kid) out.add(kid);
  }
  return out;
}

function GraphPane({
  width,
  height,
  nodes,
  edges,
  selectedId,
  highlighted,
  selectedEdgeId,
  linkFrom,
  dragId,
  onNodeDown,
  onNodeUp,
  onEdgeClick,
  onBgPointerMove,
  classPrefix,
  showEdgeLabels,
}: {
  width: number;
  height: number;
  nodes: Array<{
    id: string;
    label: string;
    kind?: string;
    type?: string;
    x: number;
    y: number;
    isolate?: boolean;
  }>;
  edges: Array<{ id: string; source: string; target: string; label?: string; type?: string; user_created?: boolean }>;
  selectedId: string | null;
  highlighted: Set<string>;
  selectedEdgeId: string | null;
  linkFrom: string | null;
  dragId: string | null;
  onNodeDown: (e: ReactPointerEvent, id: string) => void;
  onNodeUp: (e: ReactPointerEvent, id: string) => void;
  onEdgeClick?: (id: string) => void;
  onBgPointerMove: (e: ReactPointerEvent) => void;
  classPrefix: string;
  showEdgeLabels: boolean;
}) {
  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  return (
    <svg
      className={`${classPrefix}-svg`}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      onPointerMove={onBgPointerMove}
    >
      {edges.map((e) => {
        const s = byId.get(e.source);
        const t = byId.get(e.target);
        if (!s || !t) return null;
        const active = selectedEdgeId === e.id;
        const hi =
          highlighted.has(e.source) && highlighted.has(e.target);
        return (
          <g
            key={e.id}
            className={`${classPrefix}-edge-g ${active || hi ? "active" : ""}`}
            onClick={() => onEdgeClick?.(e.id)}
            style={{ cursor: onEdgeClick ? "pointer" : "default" }}
          >
            <line
              x1={s.x}
              y1={s.y}
              x2={t.x}
              y2={t.y}
              className={`${classPrefix}-edge ${e.user_created ? "user" : ""} ${
                e.label === "CONTAINS" || e.type === "CONTAINS" ? "spoke" : ""
              } ${e.type === "DEPENDS_ON" || e.label === "DEPENDS_ON" ? "depends" : ""} ${
                e.type === "CALLS" || e.label === "CALLS" ? "calls" : ""
              } ${e.type === "USES" || e.label === "USES" ? "uses" : ""} ${
                e.type === "NEXT" || e.label === "NEXT" ? "next" : ""
              } ${active || hi ? "lit" : ""}`}
            />
            {showEdgeLabels &&
            (e.label || e.type) &&
            e.label !== "CONTAINS" &&
            e.type !== "CONTAINS" &&
            e.label !== "DEPENDS_ON" ? (
              <text
                x={(s.x + t.x) / 2}
                y={(s.y + t.y) / 2 - 8}
                className={`${classPrefix}-edge-label`}
              >
                {e.label || e.type}
              </text>
            ) : null}
          </g>
        );
      })}
      {nodes.map((n) => {
        const isSelected = selectedId === n.id;
        const isHi = highlighted.has(n.id);
        const isFocus = isSelected || isHi || linkFrom === n.id;
        const baseR = n.kind === "plc_project" ? 22 : 16;
        const maxChars = n.isolate ? 10 : 16;
        return (
          <g
            key={n.id}
            className={`${classPrefix}-node ${n.kind || n.type || ""} ${
              n.isolate ? "isolate" : "galaxy"
            } ${isSelected ? "selected" : ""} ${isHi ? "highlighted" : ""} ${
              linkFrom === n.id ? "linking" : ""
            }`}
            onPointerDown={(e) => onNodeDown(e, n.id)}
            onPointerUp={(e) => onNodeUp(e, n.id)}
            style={{ cursor: dragId === n.id ? "grabbing" : "grab" }}
          >
            <title>{n.label}</title>
            <circle cx={n.x} cy={n.y} r={isFocus ? baseR + 4 : baseR} />
            <text
              x={n.x}
              y={n.y + (isFocus ? 32 : 28)}
              textAnchor="middle"
              fontWeight={isFocus ? 700 : undefined}
            >
              {shortLabel(n.label, maxChars)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export default function KnowledgeCanvas({
  data,
  logicGraph,
  onChange,
  onDeepDive,
  onNodeDescribe,
  busy,
}: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedLogicId, setSelectedLogicId] = useState<string | null>(null);
  const [selectedLogicEdge, setSelectedLogicEdge] = useState<string | null>(null);
  const [highlighted, setHighlighted] = useState<Set<string>>(new Set());
  const [dragId, setDragId] = useState<string | null>(null);
  const [moved, setMoved] = useState(false);
  const [deepQ, setDeepQ] = useState("");
  /** Left pane (logic) width %. */
  const [splitPct, setSplitPct] = useState(loadKgSplitPct);
  const dragOrigin = useRef<{ x: number; y: number; nx: number; ny: number } | null>(null);
  const svgHost = useRef<HTMLDivElement | null>(null);
  const splitHost = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    localStorage.setItem(KG_SPLIT_KEY, String(Math.round(splitPct)));
  }, [splitPct]);

  const laidOutKnowledge = useMemo(() => data.nodes, [data.nodes]);

  const logicLaid = useMemo(
    () => (logicGraph ? logicLayout(logicGraph) : { nodes: [], edges: [] }),
    [logicGraph],
  );

  const byId = useMemo(
    () => new Map(laidOutKnowledge.map((n) => [n.id, n])),
    [laidOutKnowledge],
  );
  const selected = selectedId ? byId.get(selectedId) : undefined;

  const knowledgeSize = useMemo(() => {
    const maxX = Math.max(640, ...laidOutKnowledge.map((n) => n.x + 80), 0);
    const maxY = Math.max(420, ...laidOutKnowledge.map((n) => n.y + 60), 0);
    return { w: maxX, h: maxY };
  }, [laidOutKnowledge]);

  const logicSize = useMemo(() => {
    const maxX = Math.max(640, ...logicLaid.nodes.map((n) => n.x + 80), 0);
    const maxY = Math.max(420, ...logicLaid.nodes.map((n) => n.y + 60), 0);
    return { w: maxX, h: maxY };
  }, [logicLaid.nodes]);

  useEffect(() => {
    if (selectedId && !byId.has(selectedId)) setSelectedId(null);
  }, [byId, selectedId]);

  function clientToLocal(e: ReactPointerEvent, host: HTMLElement | null) {
    if (!host) return { x: 0, y: 0 };
    const svg =
      (host.querySelector("svg.kg-svg") as SVGSVGElement | null) ||
      (host.querySelector("svg") as SVGSVGElement | null);
    if (!svg) return { x: 0, y: 0 };
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const ctm = svg.getScreenCTM();
    if (!ctm) return { x: 0, y: 0 };
    const local = pt.matrixTransform(ctm.inverse());
    return { x: local.x, y: local.y };
  }

  function onKnowledgeDown(e: ReactPointerEvent, id: string) {
    e.stopPropagation();
    e.currentTarget.setPointerCapture(e.pointerId);
    const node = byId.get(id);
    if (!node) return;
    const p = clientToLocal(e, svgHost.current);
    dragOrigin.current = { x: p.x, y: p.y, nx: node.x, ny: node.y };
    setDragId(id);
    setMoved(false);
  }

  function onKnowledgeMove(e: ReactPointerEvent) {
    if (!dragId || !dragOrigin.current) return;
    const p = clientToLocal(e, svgHost.current);
    const dx = p.x - dragOrigin.current.x;
    const dy = p.y - dragOrigin.current.y;
    if (Math.hypot(dx, dy) > 3) setMoved(true);
    const nx = Math.max(28, dragOrigin.current.nx + dx);
    const ny = Math.max(28, dragOrigin.current.ny + dy);
    onChange({
      ...data,
      nodes: data.nodes.map((n) => (n.id === dragId ? { ...n, x: nx, y: ny } : n)),
    });
  }

  function onKnowledgeUp(e: ReactPointerEvent, id: string) {
    if (dragId) {
      e.currentTarget.releasePointerCapture(e.pointerId);
      setDragId(null);
      dragOrigin.current = null;
    }
    if (moved) return;
    const node = byId.get(id);
    if (!node) return;
    setSelectedId(id);
    setSelectedLogicId(null);
    setSelectedLogicEdge(null);
    // Cross-highlight: selecting a knowledge block lights matching logic nodes
    if (node.kind === "plc_block") {
      const name = node.source?.block_name || node.label;
      const logicIds = logicLaid.nodes
        .filter((ln) => ln.label === name || ln.id.endsWith(`::${name}`))
        .map((ln) => ln.id);
      if (logicIds[0]) setSelectedLogicId(logicIds[0]);
      setHighlighted(new Set([id, ...logicIds]));
      if (!busy && onNodeDescribe) void onNodeDescribe(node);
    } else {
      setHighlighted(new Set([id]));
    }
  }

  function onLogicNodeUp(_e: ReactPointerEvent, id: string) {
    setSelectedLogicId(id);
    setSelectedLogicEdge(null);
    const kn = matchKnowledgeIds(data.nodes, [id]);
    const firstKn = [...kn][0] || null;
    setSelectedId(firstKn);
    setHighlighted(new Set([...kn, id]));
    const node = firstKn ? byId.get(firstKn) : undefined;
    if (node?.kind === "plc_block" && !busy && onNodeDescribe) {
      void onNodeDescribe(node);
    }
  }

  function onLogicEdgeClick(edgeId: string) {
    setSelectedLogicEdge(edgeId);
    setSelectedLogicId(null);
    const edge = logicLaid.edges.find((e) => e.id === edgeId);
    if (!edge) return;
    const kn = matchKnowledgeIds(data.nodes, [edge.source, edge.target]);
    setHighlighted(new Set([...kn, edge.source, edge.target]));
  }

  function onSplitPointerDown(e: ReactPointerEvent<HTMLDivElement>) {
    e.preventDefault();
    const host = splitHost.current;
    if (!host) return;
    const el = e.currentTarget;
    el.setPointerCapture(e.pointerId);
    const rect = host.getBoundingClientRect();
    const move = (ev: PointerEvent) => {
      const pct = ((ev.clientX - rect.left) / rect.width) * 100;
      setSplitPct(Math.min(75, Math.max(25, pct)));
    };
    const up = (ev: PointerEvent) => {
      el.releasePointerCapture(ev.pointerId);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  async function onDeepSubmit(e: FormEvent) {
    e.preventDefault();
    if (!selected || !deepQ.trim() || busy) return;
    const q = deepQ.trim();
    setDeepQ("");
    await onDeepDive(selected, q);
  }

  const knowledgeEdges = data.edges.filter((e) => {
    const label = e.label || "";
    // Galaxy = functional dependencies between blocks (+ user links).
    if (e.user_created) return true;
    if (label === "DEPENDS_ON" || label === "INSTANCE_OF") return true;
    return false;
  });
  const hasSelection =
    Boolean(selectedId || selectedLogicId || selectedLogicEdge) || highlighted.size > 0;

  return (
    <div className="kg-wrap">
      <div
        className={`kg-panes mode-both${hasSelection ? " has-selection" : ""}`}
        ref={(el) => {
          svgHost.current = el;
          splitHost.current = el;
        }}
      >
        <div
          className="kg-pane"
          style={{ flex: `0 0 ${splitPct}%`, width: `${splitPct}%` }}
        >
          <div className="kg-pane-title">逻辑图</div>
          <div className="kg-scroll">
            {logicLaid.nodes.length ? (
              <GraphPane
                width={logicSize.w}
                height={logicSize.h}
                nodes={logicLaid.nodes.map((n) => ({
                  ...n,
                  kind: n.type === "Block" ? "plc_block" : "plc_tag",
                }))}
                edges={logicLaid.edges.map((e) => ({
                  id: e.id,
                  source: e.source,
                  target: e.target,
                  label: e.type,
                }))}
                selectedId={selectedLogicId}
                highlighted={highlighted}
                selectedEdgeId={selectedLogicEdge}
                linkFrom={null}
                dragId={null}
                onNodeDown={() => undefined}
                onNodeUp={onLogicNodeUp}
                onEdgeClick={onLogicEdgeClick}
                onBgPointerMove={() => undefined}
                classPrefix="lg"
                showEdgeLabels={logicLaid.edges.length <= 30}
              />
            ) : (
              <p className="empty kg-empty">暂无逻辑图</p>
            )}
          </div>
        </div>
        <div
          className="kg-split"
          role="separator"
          aria-orientation="vertical"
          aria-valuenow={Math.round(splitPct)}
          aria-valuemin={25}
          aria-valuemax={75}
          aria-label="调整逻辑图与知识图谱宽度"
          title="拖动调节 · 双击恢复默认"
          onPointerDown={onSplitPointerDown}
          onDoubleClick={() => setSplitPct(KG_SPLIT_DEFAULT)}
        />
        <div
          className="kg-pane"
          style={{ flex: `1 1 ${100 - splitPct}%`, width: `${100 - splitPct}%` }}
        >
          <div className="kg-pane-title">知识图谱</div>
          <div className="kg-scroll">
            {laidOutKnowledge.length ? (
              <GraphPane
                width={knowledgeSize.w}
                height={knowledgeSize.h}
                nodes={laidOutKnowledge}
                edges={knowledgeEdges}
                selectedId={selectedId}
                highlighted={highlighted}
                selectedEdgeId={null}
                linkFrom={null}
                dragId={dragId}
                onNodeDown={onKnowledgeDown}
                onNodeUp={onKnowledgeUp}
                onBgPointerMove={onKnowledgeMove}
                classPrefix="kg"
                showEdgeLabels={knowledgeEdges.length <= 24}
              />
            ) : (
              <p className="empty kg-empty">暂无知识图谱</p>
            )}
          </div>
        </div>
      </div>

      {selected ? (
        <div className="kg-pop" role="dialog" aria-label="知识节点">
          <div className="kg-pop-head">
            <strong>{selected.label}</strong>
            <button type="button" className="ghost compact" onClick={() => setSelectedId(null)}>
              关闭
            </button>
          </div>
          <p className="kg-summary">{selected.summary}</p>
          <div className="kg-source">
            <div className="k">来源</div>
            <div className="v">
              {selected.source?.type || "dialogue"}
              {selected.source?.block_type ? ` · ${selected.source.block_type}` : ""}
              {selected.source?.project ? ` · ${selected.source.project}` : ""}
            </div>
            {selected.source?.path ? <pre className="kg-quote">{selected.source.path}</pre> : null}
            {selected.source?.quote ? <pre className="kg-quote">{selected.source.quote}</pre> : null}
          </div>
          <form className="kg-deep" onSubmit={onDeepSubmit}>
            <input
              value={deepQ}
              onChange={(e) => setDeepQ(e.target.value)}
              placeholder="就此节点深入追问…"
              disabled={busy}
            />
            <button
              type="button"
              className="ghost compact"
              disabled={busy}
              onClick={() => {
                if (!selected || busy) return;
                void onDeepDive(selected, "请描述这个功能块的作用、输入输出与主要逻辑");
              }}
            >
              描述功能
            </button>
            <button type="submit" disabled={busy || !deepQ.trim()}>
              深入
            </button>
          </form>
        </div>
      ) : null}
    </div>
  );
}
