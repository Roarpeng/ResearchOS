import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";

export type KnowledgeSource = {
  type?: string;
  role?: string;
  quote?: string;
  task_id?: string;
  turn_id?: string;
  block_name?: string;
  block_type?: string;
  entity_kind?: string;
  instance_of?: string | null;
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
  /** Connected-component galaxy index (0-based); set by autoLayoutKnowledge. */
  galaxy?: number;
  /** Hop distance from galaxy hub (0 = hub). */
  ring?: number;
  /** Highest-degree node in its galaxy. */
  hub?: boolean;
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

export type PlcKnowledgeGraphData = {
  nodes?: Array<{
    id?: string;
    type?: string;
    props?: Record<string, unknown>;
  }>;
  edges?: Array<{
    source?: string;
    target?: string;
    type?: string;
    props?: Record<string, unknown>;
  }>;
};

type Props = {
  data: KnowledgeCanvasData;
  logicGraph?: LogicGraphData | null;
  /** Full PLC KG — used to overlay IO/signal subgraph when a block is selected. */
  knowledgeGraph?: PlcKnowledgeGraphData | null;
  onChange: (next: KnowledgeCanvasData) => void;
  onDeepDive: (node: KnowledgeNode, question: string) => Promise<void> | void;
  /** Optional: auto-describe when a PLC block node is clicked (not dragged). */
  onNodeDescribe?: (node: KnowledgeNode) => Promise<void> | void;
  busy?: boolean;
};

/** Build ephemeral Tag / interface Variable nodes + READS/WRITES around a focus block. */
export function buildSignalSubgraph(
  knowledgeGraph: PlcKnowledgeGraphData | null | undefined,
  focus: KnowledgeNode | undefined,
  maxSignals = 16,
): { nodes: KnowledgeNode[]; edges: KnowledgeEdge[] } {
  if (!knowledgeGraph || !focus) return { nodes: [], edges: [] };
  const kind = String(focus.kind || "");
  if (
    kind &&
    !["plc_block", "plc_ob", "plc_db", "plc_udt", "plc_instance"].includes(kind)
  ) {
    return { nodes: [], edges: [] };
  }
  const blockName = String(focus.source?.block_name || focus.label || "").trim();
  if (!blockName) return { nodes: [], edges: [] };
  const bid = `Block::${blockName}`;
  const tagMeta = new Map<
    string,
    { name: string; address?: string; comment?: string; modes: Set<string> }
  >();
  for (const e of knowledgeGraph.edges || []) {
    const et = String(e.type || "");
    if (et !== "READS" && et !== "WRITES") continue;
    if (String(e.source || "") !== bid) continue;
    const tid = String(e.target || "");
    if (!tid.startsWith("Tag::")) continue;
    const name = tid.slice(5);
    const cur = tagMeta.get(name) || { name, modes: new Set<string>() };
    cur.modes.add(et);
    tagMeta.set(name, cur);
  }
  for (const n of knowledgeGraph.nodes || []) {
    if (String(n.type || "") !== "Tag") continue;
    const props = (n.props || {}) as Record<string, unknown>;
    const name = String(props.name || String(n.id || "").split("::").pop() || "");
    const cur = tagMeta.get(name);
    if (!cur) continue;
    if (props.address) cur.address = String(props.address);
    if (props.comment) cur.comment = String(props.comment);
  }
  // Interface variables when few tag edges
  if (tagMeta.size < 4) {
    for (const e of knowledgeGraph.edges || []) {
      if (String(e.type || "") !== "HAS_INTERFACE") continue;
      if (String(e.source || "") !== bid) continue;
      const vid = String(e.target || "");
      if (!vid.startsWith("Variable::")) continue;
      const props =
        (
          (knowledgeGraph.nodes || []).find((n) => n.id === vid)?.props || {}
        ) as Record<string, unknown>;
      const name = String(props.name || vid.split("::").pop() || "");
      if (!name || tagMeta.has(`#${name}`) || tagMeta.has(name)) continue;
      const section = String(props.section || "").toLowerCase();
      const modes = new Set<string>();
      if (section.includes("out")) modes.add("WRITES");
      else modes.add("READS");
      if (section.includes("inout")) {
        modes.add("READS");
        modes.add("WRITES");
      }
      tagMeta.set(`#${name}`, {
        name: `#${name}`,
        comment: String(props.data_type || section || "interface"),
        modes,
      });
    }
  }
  const entries = [...tagMeta.values()].slice(0, maxSignals);
  if (!entries.length) return { nodes: [], edges: [] };
  const cx = focus.x;
  const cy = focus.y;
  const nodes: KnowledgeNode[] = [];
  const edges: KnowledgeEdge[] = [];
  entries.forEach((t, i) => {
    const angle = -Math.PI / 2 + (2 * Math.PI * i) / Math.max(entries.length, 1);
    const r = 88 + (entries.length > 8 ? 18 : 0);
    const id = `sig_${focus.id}_${t.name}`;
    const modeLabel = [...t.modes].join("/");
    nodes.push({
      id,
      label: t.name,
      summary: [modeLabel, t.address, t.comment].filter(Boolean).join(" · ").slice(0, 120),
      kind: "plc_tag",
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
      source: {
        type: "plc",
        quote: t.name,
        block_name: blockName,
        plc_job_id: focus.source?.plc_job_id,
        project: focus.source?.project,
      },
      isolate: true,
    });
    for (const mode of t.modes) {
      edges.push({
        id: `sig_e_${id}_${mode}`,
        source: focus.id,
        target: id,
        label: mode,
        user_created: false,
      });
    }
  });
  return { nodes, edges };
}

const COL_W = 160;
const ROW_H = 100;
const MARGIN = 56;
/** Minimum center-to-center gap so labels do not collide in the galaxy view. */
const GALAXY_MIN_SEP = 128;

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
    return Math.min(100, Math.max(0, n));
  } catch {
    return KG_SPLIT_DEFAULT;
  }
}

function clampSplitPct(n: number): number {
  if (!Number.isFinite(n)) return KG_SPLIT_DEFAULT;
  // Snap to edges so one pane can fully hide
  if (n < 4) return 0;
  if (n > 96) return 100;
  return Math.min(100, Math.max(0, n));
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

function pairMinSep(a: KnowledgeNode, b: KnowledgeNode): number {
  const la = Math.min(String(a.label || "").length, 20);
  const lb = Math.min(String(b.label || "").length, 20);
  // Account for label under node (~5.5px/char) + node radius
  return Math.max(GALAXY_MIN_SEP, 56 + Math.max(la, lb) * 5.2);
}

/** Iterative repulsion so galaxy nodes never sit on top of each other. */
function separateGalaxyNodes(nodes: KnowledgeNode[], iterations = 56): KnowledgeNode[] {
  const pts = nodes.map((n) => ({ ...n }));
  for (let iter = 0; iter < iterations; iter++) {
    for (let i = 0; i < pts.length; i++) {
      for (let j = i + 1; j < pts.length; j++) {
        const a = pts[i];
        const b = pts[j];
        if (a.isolate || b.isolate) continue;
        if (a.galaxy !== undefined && b.galaxy !== undefined && a.galaxy !== b.galaxy) {
          // Different systems: keep galaxies from merging
          const need = Math.max(pairMinSep(a, b) + 40, 200);
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const d = Math.hypot(dx, dy) || 0.01;
          if (d >= need) continue;
          const push = (need - d) / 2;
          const ux = dx / d;
          const uy = dy / d;
          a.x -= ux * push;
          a.y -= uy * push;
          b.x += ux * push;
          b.y += uy * push;
          continue;
        }
        const need = pairMinSep(a, b);
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const d = Math.hypot(dx, dy) || 0.01;
        if (d >= need) continue;
        const push = (need - d) / 2;
        const ux = dx / d;
        const uy = dy / d;
        // Keep hub closer to center: move satellites more
        const aw = a.hub ? 0.25 : 0.5;
        const bw = b.hub ? 0.25 : 0.5;
        a.x -= ux * push * (aw / (aw + bw)) * 2;
        a.y -= uy * push * (aw / (aw + bw)) * 2;
        b.x += ux * push * (bw / (aw + bw)) * 2;
        b.y += uy * push * (bw / (aw + bw)) * 2;
      }
    }
  }
  return pts;
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

const PLC_GRAPH_KINDS = new Set([
  "plc_block",
  "plc_ob",
  "plc_db",
  "plc_udt",
  "plc_tag",
  "plc_instance",
]);

/** Semantic PLC node class for canvas color (block *types*, not each FB name). */
export type PlcGraphType =
  | "OB"
  | "FB"
  | "FC"
  | "GDB"
  | "IDB"
  | "UDT"
  | "TAG"
  | "PROJECT"
  | "OTHER";

const GRAPH_TYPE_ORDER: PlcGraphType[] = [
  "OB",
  "FB",
  "FC",
  "GDB",
  "IDB",
  "UDT",
  "TAG",
  "PROJECT",
  "OTHER",
];

const GRAPH_TYPE_LABEL: Record<PlcGraphType, string> = {
  OB: "OB",
  FB: "FB",
  FC: "FC",
  GDB: "全局 DB",
  IDB: "实例 DB",
  UDT: "UDT",
  TAG: "标签",
  PROJECT: "工程",
  OTHER: "其他",
};

type GraphTypeNode = {
  kind?: string;
  type?: string;
  label?: string;
  blockType?: string;
  instanceOf?: string;
  source?: KnowledgeSource;
};

function rawBlockType(n: GraphTypeNode): string {
  return String(n.blockType || n.source?.block_type || "")
    .trim()
    .toUpperCase()
    .replace(/^SW\.BLOCKS\./, "")
    .replace(/^PLC_/, "");
}

/** Map IR / KG fields → one color class. Instance DB ≠ Global DB. */
export function resolveGraphType(n: GraphTypeNode): PlcGraphType {
  const kind = String(n.kind || "");
  if (kind === "plc_project") return "PROJECT";
  if (kind === "plc_tag" || n.type === "TagTable" || n.type === "Tag") return "TAG";
  if (kind === "plc_udt") return "UDT";
  if (kind === "plc_instance" || n.source?.entity_kind === "instance") return "IDB";

  const inst = String(n.instanceOf || n.source?.instance_of || "").trim();
  const raw = rawBlockType(n);

  if (raw === "UDT" || raw === "PLCSTRUCT" || raw === "STRUCT") return "UDT";
  if (raw === "OB") return "OB";
  if (raw === "FC") return "FC";
  if (raw === "FB") return "FB";
  if (
    raw === "INSTANCEDB" ||
    raw === "INSTANCE_DB" ||
    raw === "IDB" ||
    raw === "INSTANCE"
  ) {
    return "IDB";
  }
  if (raw === "GLOBALDB" || raw === "GLOBAL_DB" || raw === "GDB" || raw === "ARRAYDB") {
    return "GDB";
  }
  if (raw === "DB" || kind === "plc_db") return inst ? "IDB" : "GDB";
  if (kind === "plc_ob") return "OB";
  if (kind === "plc_block") return raw ? "OTHER" : "FB";
  return "OTHER";
}

function graphTypesPresent(nodes: GraphTypeNode[]): PlcGraphType[] {
  const seen = new Set<PlcGraphType>();
  nodes.forEach((n) => seen.add(resolveGraphType(n)));
  return GRAPH_TYPE_ORDER.filter((t) => seen.has(t));
}

type ViewBox = { x: number; y: number; w: number; h: number };

function worldBounds(
  nodes: Array<{ x: number; y: number }>,
  fallbackW: number,
  fallbackH: number,
) {
  if (!nodes.length) {
    return { minX: 0, minY: 0, maxX: fallbackW, maxY: fallbackH };
  }
  const xs = nodes.map((n) => n.x);
  const ys = nodes.map((n) => n.y);
  return {
    minX: Math.min(...xs) - 56,
    minY: Math.min(...ys) - 48,
    maxX: Math.max(...xs) + 88,
    maxY: Math.max(...ys) + 64,
  };
}

function fitViewBox(
  bounds: { minX: number; minY: number; maxX: number; maxY: number },
  clientW: number,
  clientH: number,
  pad = 1.08,
): ViewBox {
  const bw = Math.max(160, bounds.maxX - bounds.minX);
  const bh = Math.max(120, bounds.maxY - bounds.minY);
  const cw = Math.max(1, clientW);
  const ch = Math.max(1, clientH);
  const scale = Math.min(cw / (bw * pad), ch / (bh * pad));
  const safe = Math.max(scale, 1e-6);
  const vw = cw / safe;
  const vh = ch / safe;
  const cx = (bounds.minX + bounds.maxX) / 2;
  const cy = (bounds.minY + bounds.maxY) / 2;
  return { x: cx - vw / 2, y: cy - vh / 2, w: vw, h: vh };
}

function clampViewBox(
  box: ViewBox,
  bounds: { minX: number; minY: number; maxX: number; maxY: number },
  clientW: number,
  clientH: number,
): ViewBox {
  const worldW = Math.max(160, bounds.maxX - bounds.minX);
  const worldH = Math.max(120, bounds.maxY - bounds.minY);
  const cw = Math.max(1, clientW);
  const ch = Math.max(1, clientH);
  const fitScale = Math.min(cw / worldW, ch / worldH);
  const minScale = fitScale * 0.2;
  const maxScale = Math.max(fitScale * 10, 2.5);
  let scale = cw / Math.max(box.w, 1);
  scale = Math.min(maxScale, Math.max(minScale, scale));
  const w = cw / scale;
  const h = ch / scale;
  return { x: box.x, y: box.y, w, h };
}

function zoomViewBox(box: ViewBox, mx: number, my: number, factor: number): ViewBox {
  const nw = box.w / factor;
  const nh = box.h / factor;
  return {
    x: mx - ((mx - box.x) * nw) / box.w,
    y: my - ((my - box.y) * nh) / box.h,
    w: nw,
    h: nh,
  };
}

/** PLC implementation graph only — hide chat insights / questions / project hub. */
export function isPlcGraphNode(n: {
  kind?: string;
  source?: { type?: string; block_name?: string };
}): boolean {
  const kind = String(n.kind || "");
  if (PLC_GRAPH_KINDS.has(kind)) return true;
  // Legacy nodes: plc source with a block name, but not dialogue snippets
  if (n.source?.type === "plc" && n.source.block_name) return true;
  return false;
}

/**
 * Galaxy layout: cluster by functional dependency edges.
 * Connected components → mini-galaxies (hub + orbital rings);
 * degree-0 PLC isolates → bottom strip.
 * Dialogue insight/question nodes are excluded from this view.
 */
export function autoLayoutKnowledge(
  nodes: KnowledgeNode[],
  edges: KnowledgeEdge[] = [],
): KnowledgeNode[] {
  const plcNodes = nodes.filter(isPlcGraphNode);
  const project = plcNodes.filter((n) => n.kind === "plc_project");
  const blocks = plcNodes.filter(
    (n) =>
      n.kind === "plc_block" ||
      n.kind === "plc_tag" ||
      n.kind === "plc_ob" ||
      n.kind === "plc_db" ||
      n.kind === "plc_udt" ||
      n.kind === "plc_instance",
  );
  const byId = new Map(plcNodes.map((n) => [n.id, n]));
  const blockIds = blocks.map((n) => n.id);
  const idSet = new Set(blockIds);
  const depEdges = edges.filter((e) => {
    if (!idSet.has(e.source) || !idSet.has(e.target)) return false;
    const lab = e.label || "";
    return (
      lab === "DEPENDS_ON" ||
      lab === "INSTANCE_OF" ||
      lab === "CALLS" ||
      lab === "USES" ||
      e.user_created
    );
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
  const maxComp = Math.max(1, ...galaxies.map((c) => c.length));
  // Radius needed for densest ring of largest galaxy (chord ≈ GALAXY_MIN_SEP)
  const densestRingR = Math.max(
    180,
    (Math.min(maxComp, 14) * GALAXY_MIN_SEP) / (2 * Math.PI) + 40,
  );
  const systemSpan = densestRingR * 2 + 160 + Math.min(maxComp, 40) * 8;
  const orbitR =
    galaxyCount > 1
      ? Math.max(systemSpan * 0.65, 420) + Math.min(galaxyCount, 8) * 48
      : 0;

  galaxies.forEach((comp, gi) => {
    const angle = -Math.PI / 2 + (2 * Math.PI * gi) / galaxyCount;
    const gcx = 640 + (galaxyCount > 1 ? orbitR * Math.cos(angle) : 0);
    const gcy = 480 + (galaxyCount > 1 ? orbitR * Math.sin(angle) * 0.88 : 0);

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
        if (n) {
          out.push({
            ...n,
            isolate: false,
            galaxy: gi,
            ring: 0,
            hub: true,
            x: gcx,
            y: gcy,
          });
        }
        return;
      }
      // Cap nodes per physical orbit; overflow → outer sub-rings (prevents sticking)
      const maxPerOrbit = 10;
      sorted.forEach((id, i) => {
        const node = byId.get(id);
        if (!node) return;
        const sub = Math.floor(i / maxPerOrbit);
        const idx = i % maxPerOrbit;
        const inSub = Math.min(maxPerOrbit, sorted.length - sub * maxPerOrbit);
        const radius = Math.max(
          100 + ring * 140 + sub * 120,
          (inSub * GALAXY_MIN_SEP) / (2 * Math.PI) + 36,
        );
        const a = -Math.PI / 2 + (2 * Math.PI * idx) / inSub + (sub * 0.11);
        out.push({
          ...node,
          isolate: false,
          galaxy: gi,
          ring: ring + sub * 0.01,
          hub: false,
          x: gcx + radius * Math.cos(a),
          y: gcy + radius * Math.sin(a),
        });
      });
    });
  });

  const orphanBaseY =
    (out.length ? Math.max(...out.map((n) => n.y)) : 400) + 220;
  orphans
    .slice()
    .sort((a, b) => (byId.get(a)?.label || "").localeCompare(byId.get(b)?.label || ""))
    .forEach((id, i) => {
      const node = byId.get(id);
      if (!node) return;
      const cols = Math.min(8, Math.max(4, Math.ceil(Math.sqrt(orphans.length))));
      out.push({
        ...node,
        isolate: true,
        galaxy: undefined,
        ring: undefined,
        hub: false,
        x: MARGIN + 48 + (i % cols) * Math.max(COL_W, GALAXY_MIN_SEP + 20),
        y: orphanBaseY + Math.floor(i / cols) * Math.max(ROW_H, 96),
      });
    });

  project.forEach((n, i) => {
    const label = String(n.label || "").trim();
    if (!label || /^[a-f0-9]{5,}$/i.test(label) || /^plc[_-]/i.test(label)) return;
    out.push({
      ...n,
      isolate: false,
      hub: false,
      x: MARGIN + 40 + i * 160,
      y: MARGIN + 20,
    });
  });

  return normalizePad(separateGalaxyNodes(out));
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
 * PLC scan-cycle layout — **逻辑图**:
 * - Vertical spine: OB → step1 → step2 … (call sequence top → bottom)
 * - Parallel (same Y): callees that mutually USE / CALL each other
 */
function logicLayout(
  graph: LogicGraphData,
  mutualHints: Array<{ source: string; target: string; label?: string }> = [],
): {
  nodes: Array<{
    id: string;
    label: string;
    type?: string;
    kind?: string;
    blockType?: string;
    instanceOf?: string;
    x: number;
    y: number;
  }>;
  edges: Array<{ id: string; source: string; target: string; type: string }>;
} {
  const blockNodes = (graph.nodes || []).filter((n) => n.type === "Block");
  const byId = new Map(blockNodes.map((n) => [n.id, n]));
  const ids = new Set(blockNodes.map((n) => n.id));
  const shortOf = (id: string) => (id.includes("::") ? id.split("::").pop() || id : id);

  const calls = (graph.edges || []).filter(
    (e) => e.type === "CALLS" && ids.has(e.source) && ids.has(e.target),
  );
  const nexts = (graph.edges || []).filter(
    (e) => e.type === "NEXT" && ids.has(e.source) && ids.has(e.target),
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

  // Mutual-use among blocks (from knowledge edges or logic CALLS both ways)
  const mutual = new Map<string, Set<string>>();
  const linkMutual = (a: string, b: string) => {
    if (!a || !b || a === b) return;
    if (!mutual.has(a)) mutual.set(a, new Set());
    if (!mutual.has(b)) mutual.set(b, new Set());
    mutual.get(a)!.add(b);
    mutual.get(b)!.add(a);
  };
  mutualHints.forEach((e) => {
    const lab = e.label || "";
    if (lab !== "USES" && lab !== "CALLS" && lab !== "DEPENDS_ON") return;
    // Resolve by id or short label against logic nodes
    const sa = [...ids].find((id) => id === e.source || shortOf(id) === e.source || shortOf(id) === shortOf(e.source));
    const sb = [...ids].find((id) => id === e.target || shortOf(id) === e.target || shortOf(id) === shortOf(e.target));
    if (sa && sb) linkMutual(sa, sb);
  });
  // Bidirectional CALLS in logic graph also count as mutual
  const callPairs = new Set(calls.map((e) => `${e.source}>${e.target}`));
  calls.forEach((e) => {
    if (callPairs.has(`${e.target}>${e.source}`)) linkMutual(e.source, e.target);
  });

  const obs = blockNodes.filter(isObNode);
  const mainOb =
    obs.find(isMainCycleOb) ||
    [...obs].sort(
      (a, b) => (callOut.get(b.id)?.length || 0) - (callOut.get(a.id)?.length || 0),
    )[0] ||
    null;

  const STEP_Y = 150;
  const PARALLEL_X = 200;
  const CENTER_X = MARGIN + 280;
  const placed = new Map<string, { x: number; y: number; step?: number; lane: string }>();

  function uniqueSpine(obId: string): string[] {
    const spine = callOut.get(obId) || [];
    const uniq: string[] = [];
    spine.forEach(({ tgt }) => {
      if (!uniq.includes(tgt)) uniq.push(tgt);
    });
    return uniq;
  }

  /** Group ordered spine into vertical bands; mutual peers share a band (parallel). */
  function parallelBands(spine: string[]): string[][] {
    const order = new Map(spine.map((id, i) => [id, i]));
    const remaining = new Set(spine);
    const bands: string[][] = [];
    while (remaining.size) {
      const seed = spine.find((id) => remaining.has(id))!;
      const band = [seed];
      remaining.delete(seed);
      let grew = true;
      while (grew) {
        grew = false;
        for (const id of spine) {
          if (!remaining.has(id)) continue;
          if (band.some((b) => mutual.get(b)?.has(id))) {
            band.push(id);
            remaining.delete(id);
            grew = true;
          }
        }
      }
      band.sort((a, b) => (order.get(a) || 0) - (order.get(b) || 0));
      bands.push(band);
    }
    return bands;
  }

  function placeVerticalLane(ob: { id: string }, laneIndex: number, lane: string) {
    const xShift = laneIndex * (PARALLEL_X * 3.2);
    const cx = CENTER_X + xShift;
    let y = MARGIN + 72;
    placed.set(ob.id, { x: cx, y, lane });
    y += STEP_Y;
    const bands = parallelBands(uniqueSpine(ob.id));
    let step = 1;
    bands.forEach((band) => {
      const width = (band.length - 1) * PARALLEL_X;
      band.forEach((id, i) => {
        if (placed.has(id)) return;
        placed.set(id, {
          x: cx - width / 2 + i * PARALLEL_X,
          y,
          step: step++,
          lane,
        });
      });
      y += STEP_Y;
    });
  }

  if (mainOb) {
    placeVerticalLane(mainOb, 0, "main");
  }

  let lane = 1;
  obs
    .filter((o) => o.id !== mainOb?.id)
    .forEach((ob) => {
      const seq = callOut.get(ob.id) || [];
      if (!seq.length && !mainOb) {
        placed.set(ob.id, {
          x: CENTER_X + lane * PARALLEL_X * 2,
          y: MARGIN + 72,
          lane: "other",
        });
        lane += 1;
        return;
      }
      if (!seq.length) return;
      placeVerticalLane(ob, lane, "other");
      lane += 1;
    });

  if (!placed.size) {
    blockNodes.slice(0, 24).forEach((n, i) => {
      placed.set(n.id, {
        x: CENTER_X + ((i % 3) - 1) * PARALLEL_X,
        y: MARGIN + 72 + Math.floor(i / 3) * STEP_Y,
        lane: "fallback",
      });
    });
  }

  // Final separation within lane
  const entries = [...placed.values()];
  for (let iter = 0; iter < 8; iter++) {
    for (let i = 0; i < entries.length; i++) {
      for (let j = i + 1; j < entries.length; j++) {
        const a = entries[i];
        const b = entries[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const d = Math.hypot(dx, dy) || 0.01;
        const need = Math.abs(dy) < 40 ? PARALLEL_X * 0.92 : 110;
        if (d >= need) continue;
        const push = (need - d) / 2;
        const ux = dx / d;
        const uy = dy / d;
        a.x = Math.max(MARGIN + 28, a.x - ux * push);
        a.y = Math.max(MARGIN + 28, a.y - uy * push);
        b.x = Math.max(MARGIN + 28, b.x + ux * push);
        b.y = Math.max(MARGIN + 28, b.y + uy * push);
      }
    }
  }

  const nodes = [...placed.entries()].map(([id, pos]) => {
    const n = byId.get(id)!;
    const base = n.label || id.split("::").pop() || id;
    const label = pos.step ? `${pos.step}.${base}` : base;
    const bt = String(n.props?.block_type || n.props?.type || "").toUpperCase();
    const inst = String(
      n.props?.instance_of || n.props?.InstanceOfName || n.props?.OfType || "",
    ).trim();
    const external = Boolean(n.props?.external);
    const kind =
      bt === "OB"
        ? "plc_ob"
        : bt === "UDT"
          ? "plc_udt"
          : bt === "DB" && (inst || external)
            ? "plc_instance"
            : bt === "DB"
              ? "plc_db"
              : "plc_block";
    return {
      id,
      label,
      type: n.type,
      kind,
      blockType: bt,
      instanceOf: inst || undefined,
      x: pos.x,
      y: pos.y,
    };
  });
  const showSet = new Set(placed.keys());

  const edgeList: Array<{ id: string; source: string; target: string; type: string }> = [];
  let ei = 0;
  const addE = (source: string, target: string, type: string) => {
    if (!showSet.has(source) || !showSet.has(target) || source === target) return;
    edgeList.push({ id: `lg_${ei++}_${source}_${target}`, source, target, type });
  };

  const wireOb = (obId: string) => {
    const bands = parallelBands(uniqueSpine(obId));
    const flat = bands.flat();
    flat.forEach((id) => addE(obId, id, "CALLS"));
    for (let bi = 0; bi < bands.length - 1; bi++) {
      // NEXT: last of band → first of next band (vertical flow)
      const a = bands[bi][bands[bi].length - 1];
      const b = bands[bi + 1][0];
      addE(a, b, "NEXT");
    }
    // Parallel peers: light NEXT among mutual group (optional visual)
    bands.forEach((band) => {
      for (let i = 0; i < band.length - 1; i++) {
        if (mutual.get(band[i])?.has(band[i + 1])) {
          addE(band[i], band[i + 1], "NEXT");
        }
      }
    });
  };

  if (mainOb) wireOb(mainOb.id);
  nexts.forEach((e) => {
    if (showSet.has(e.source) && showSet.has(e.target)) {
      if (!edgeList.some((x) => x.source === e.source && x.target === e.target && x.type === "NEXT")) {
        addE(e.source, e.target, "NEXT");
      }
    }
  });
  obs
    .filter((o) => o.id !== mainOb?.id)
    .forEach((ob) => {
      if (placed.has(ob.id)) wireOb(ob.id);
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

function GraphLegend({ types }: { types: PlcGraphType[] }) {
  if (!types.length) return null;
  return (
    <ul className="kg-legend" aria-label="节点类型图例">
      {types.map((t) => (
        <li key={t} className={`kg-legend-item gt-${t}`}>
          <i className="kg-legend-dot" aria-hidden />
          {GRAPH_TYPE_LABEL[t]}
        </li>
      ))}
    </ul>
  );
}

function ZoomHost({
  title,
  hint,
  layoutKey,
  nodes,
  worldW,
  worldH,
  children,
}: {
  title: string;
  hint: string;
  layoutKey: string;
  nodes: GraphTypeNode[];
  worldW: number;
  worldH: number;
  children: (args: {
    view: ViewBox;
    panning: boolean;
    onBgPointerDown: (e: ReactPointerEvent) => void;
    onBgPointerMove: (e: ReactPointerEvent) => void;
    onBgPointerUp: (e: ReactPointerEvent) => void;
  }) => ReactNode;
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const viewRef = useRef<ViewBox>({ x: 0, y: 0, w: worldW, h: worldH });
  const clientRef = useRef({ w: 1, h: 1 });
  const layoutKeyRef = useRef(layoutKey);
  const panRef = useRef<{ x: number; y: number; box: ViewBox } | null>(null);
  const pointersRef = useRef(new Map<number, { x: number; y: number }>());
  const pinchRef = useRef<{ dist: number; cx: number; cy: number; box: ViewBox } | null>(
    null,
  );
  const didFitRef = useRef(false);
  const [view, setView] = useState<ViewBox>({ x: 0, y: 0, w: worldW, h: worldH });
  const [client, setClient] = useState({ w: 1, h: 1 });
  const [panning, setPanning] = useState(false);

  const bounds = useMemo(
    () => worldBounds(nodes as Array<{ x: number; y: number }>, worldW, worldH),
    [nodes, worldW, worldH],
  );

  const applyView = useCallback(
    (next: ViewBox) => {
      const clamped = clampViewBox(next, bounds, clientRef.current.w, clientRef.current.h);
      viewRef.current = clamped;
      setView(clamped);
    },
    [bounds],
  );

  const fit = useCallback(() => {
    const { w, h } = clientRef.current;
    if (w < 8 || h < 8) return;
    applyView(fitViewBox(bounds, w, h));
  }, [applyView, bounds]);

  useEffect(() => {
    const el = hostRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect();
      const next = { w: Math.max(1, r.width), h: Math.max(1, r.height) };
      clientRef.current = next;
      setClient(next);
    });
    ro.observe(el);
    const r = el.getBoundingClientRect();
    clientRef.current = { w: Math.max(1, r.width), h: Math.max(1, r.height) };
    setClient(clientRef.current);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (client.w < 8 || client.h < 8) return;
    if (!didFitRef.current || layoutKeyRef.current !== layoutKey) {
      layoutKeyRef.current = layoutKey;
      didFitRef.current = true;
      fit();
      return;
    }
    applyView(viewRef.current);
  }, [applyView, client.h, client.w, fit, layoutKey]);

  const clientToWorld = useCallback(
    (clientX: number, clientY: number) => {
      const el = hostRef.current;
      if (!el) return { x: 0, y: 0 };
      const rect = el.getBoundingClientRect();
      const box = viewRef.current;
      return {
        x: box.x + ((clientX - rect.left) / Math.max(1, rect.width)) * box.w,
        y: box.y + ((clientY - rect.top) / Math.max(1, rect.height)) * box.h,
      };
    },
    [],
  );

  const zoomBy = useCallback(
    (factor: number, clientX?: number, clientY?: number) => {
      const el = hostRef.current;
      const rect = el?.getBoundingClientRect();
      const cx = clientX ?? (rect ? rect.left + rect.width / 2 : 0);
      const cy = clientY ?? (rect ? rect.top + rect.height / 2 : 0);
      const p = clientToWorld(cx, cy);
      applyView(zoomViewBox(viewRef.current, p.x, p.y, factor));
    },
    [applyView, clientToWorld],
  );

  useEffect(() => {
    const el = hostRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
      zoomBy(factor, e.clientX, e.clientY);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [zoomBy]);

  useEffect(() => {
    const el = hostRef.current;
    if (!el) return;
    const onDown = (e: PointerEvent) => {
      pointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (pointersRef.current.size === 2) {
        const pts = [...pointersRef.current.values()];
        pinchRef.current = {
          dist: Math.hypot(pts[1].x - pts[0].x, pts[1].y - pts[0].y) || 1,
          cx: (pts[0].x + pts[1].x) / 2,
          cy: (pts[0].y + pts[1].y) / 2,
          box: viewRef.current,
        };
        panRef.current = null;
        setPanning(false);
      }
    };
    const onMove = (e: PointerEvent) => {
      if (!pointersRef.current.has(e.pointerId)) return;
      pointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (pointersRef.current.size === 2 && pinchRef.current) {
        const pts = [...pointersRef.current.values()];
        const dist = Math.hypot(pts[1].x - pts[0].x, pts[1].y - pts[0].y) || 1;
        const factor = dist / pinchRef.current.dist;
        const cx = (pts[0].x + pts[1].x) / 2;
        const cy = (pts[0].y + pts[1].y) / 2;
        const origin = pinchRef.current.box;
        const p = {
          x: origin.x + ((pinchRef.current.cx - (el.getBoundingClientRect().left)) / Math.max(1, el.clientWidth)) * origin.w,
          y: origin.y + ((pinchRef.current.cy - (el.getBoundingClientRect().top)) / Math.max(1, el.clientHeight)) * origin.h,
        };
        const zoomed = zoomViewBox(origin, p.x, p.y, factor);
        const dx =
          ((cx - pinchRef.current.cx) / Math.max(1, el.clientWidth)) * origin.w;
        const dy =
          ((cy - pinchRef.current.cy) / Math.max(1, el.clientHeight)) * origin.h;
        applyView({ ...zoomed, x: zoomed.x - dx, y: zoomed.y - dy });
      }
    };
    const onUp = (e: PointerEvent) => {
      pointersRef.current.delete(e.pointerId);
      if (pointersRef.current.size < 2) pinchRef.current = null;
    };
    el.addEventListener("pointerdown", onDown);
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", onUp);
    el.addEventListener("pointercancel", onUp);
    return () => {
      el.removeEventListener("pointerdown", onDown);
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", onUp);
      el.removeEventListener("pointercancel", onUp);
    };
  }, [applyView]);

  function onBgPointerDown(e: ReactPointerEvent) {
    if (pointersRef.current.size >= 2) return;
    const t = e.target as Element | null;
    if (t?.closest?.("[data-kg-node]")) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    panRef.current = { x: e.clientX, y: e.clientY, box: viewRef.current };
    setPanning(true);
  }

  function onBgPointerMove(e: ReactPointerEvent) {
    if (!panRef.current || pinchRef.current) return;
    const el = hostRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const dx = ((e.clientX - panRef.current.x) / Math.max(1, rect.width)) * panRef.current.box.w;
    const dy = ((e.clientY - panRef.current.y) / Math.max(1, rect.height)) * panRef.current.box.h;
    applyView({
      ...panRef.current.box,
      x: panRef.current.box.x - dx,
      y: panRef.current.box.y - dy,
    });
  }

  function onBgPointerUp(e: ReactPointerEvent) {
    if (panRef.current) {
      try {
        e.currentTarget.releasePointerCapture(e.pointerId);
      } catch {
        /* already released */
      }
    }
    panRef.current = null;
    setPanning(false);
  }

  const types = useMemo(() => graphTypesPresent(nodes), [nodes]);

  return (
    <>
      <div className="kg-pane-title">
        {title}
        <span className="kg-pane-hint">{hint}</span>
        <GraphLegend types={types} />
        <span className="kg-zoom-tools">
          <button
            type="button"
            className="ghost compact"
            title="缩小"
            aria-label="缩小"
            onClick={() => zoomBy(1 / 1.25)}
          >
            −
          </button>
          <button
            type="button"
            className="ghost compact"
            title="查看全貌"
            aria-label="查看全貌，缩放到完整图谱"
            onClick={fit}
          >
            查看全貌
          </button>
          <button
            type="button"
            className="ghost compact"
            title="放大"
            aria-label="放大"
            onClick={() => zoomBy(1.25)}
          >
            +
          </button>
        </span>
      </div>
      <div className="kg-scroll" ref={hostRef}>
        {children({
          view,
          panning,
          onBgPointerDown,
          onBgPointerMove,
          onBgPointerUp,
        })}
      </div>
    </>
  );
}

function GraphPane({
  view,
  nodes,
  edges,
  selectedId,
  highlighted,
  selectedEdgeId,
  linkFrom,
  dragId,
  panning,
  onNodeDown,
  onNodeUp,
  onEdgeClick,
  onBgPointerDown,
  onBgPointerMove,
  onBgPointerUp,
  classPrefix,
  showEdgeLabels,
}: {
  view: ViewBox;
  nodes: Array<{
    id: string;
    label: string;
    kind?: string;
    type?: string;
    blockType?: string;
    instanceOf?: string;
    source?: KnowledgeSource;
    x: number;
    y: number;
    isolate?: boolean;
    galaxy?: number;
    ring?: number;
    hub?: boolean;
  }>;
  edges: Array<{ id: string; source: string; target: string; label?: string; type?: string; user_created?: boolean }>;
  selectedId: string | null;
  highlighted: Set<string>;
  selectedEdgeId: string | null;
  linkFrom: string | null;
  dragId: string | null;
  panning: boolean;
  onNodeDown: (e: ReactPointerEvent, id: string) => void;
  onNodeUp: (e: ReactPointerEvent, id: string) => void;
  onEdgeClick?: (id: string) => void;
  onBgPointerDown: (e: ReactPointerEvent) => void;
  onBgPointerMove: (e: ReactPointerEvent) => void;
  onBgPointerUp: (e: ReactPointerEvent) => void;
  classPrefix: string;
  showEdgeLabels: boolean;
}) {
  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  const galaxyGuides = useMemo(() => {
    if (classPrefix !== "kg") return [];
    const groups = new Map<number, typeof nodes>();
    nodes.forEach((n) => {
      if (n.isolate || n.galaxy === undefined) return;
      const list = groups.get(n.galaxy) || [];
      list.push(n);
      groups.set(n.galaxy, list);
    });
    const guides: Array<{
      gi: number;
      cx: number;
      cy: number;
      rings: number[];
      glowR: number;
      hubLabel: string;
    }> = [];
    groups.forEach((members, gi) => {
      const hub = members.find((m) => m.hub) || members[0];
      const cx = hub.x;
      const cy = hub.y;
      const ringSet = new Set<number>();
      let maxR = 48;
      members.forEach((m) => {
        if (m.ring && m.ring > 0) ringSet.add(m.ring);
        const d = Math.hypot(m.x - cx, m.y - cy);
        if (d > maxR) maxR = d;
      });
      const rings = [...ringSet].sort((a, b) => a - b).map((r) => {
        const onRing = members.filter((m) => m.ring === r);
        if (!onRing.length) return 72 + r * 96;
        return (
          onRing.reduce((s, m) => s + Math.hypot(m.x - cx, m.y - cy), 0) / onRing.length
        );
      });
      guides.push({
        gi,
        cx,
        cy,
        rings,
        glowR: maxR + 36,
        hubLabel: hub.label,
      });
    });
    return guides;
  }, [nodes, classPrefix]);

  /** Undirected pair → list of edge ids (CALLS+NEXT on same link, or A↔B). */
  const edgeLane = useMemo(() => {
    const buckets = new Map<string, string[]>();
    edges.forEach((e) => {
      const a = e.source;
      const b = e.target;
      const key = a < b ? `${a}||${b}` : `${b}||${a}`;
      const list = buckets.get(key) || [];
      list.push(e.id);
      buckets.set(key, list);
    });
    const lane = new Map<string, number>(); // -1 | 0 | 1 | …
    buckets.forEach((ids) => {
      if (ids.length === 1) {
        lane.set(ids[0], 0);
        return;
      }
      // Prefer CALLS left (-1), NEXT right (+1); else alternate by index
      const ranked = ids.slice().sort((ia, ib) => {
        const ea = edges.find((x) => x.id === ia);
        const eb = edges.find((x) => x.id === ib);
        const rank = (t: string) =>
          t === "CALLS" ? 0 : t === "NEXT" ? 1 : t === "USES" ? 2 : 3;
        return (
          rank(String(ea?.label || ea?.type || "")) -
            rank(String(eb?.label || eb?.type || "")) || ia.localeCompare(ib)
        );
      });
      ranked.forEach((id, i) => {
        if (ranked.length === 2) {
          lane.set(id, i === 0 ? -1 : 1);
        } else {
          lane.set(id, i - Math.floor((ranked.length - 1) / 2));
        }
      });
    });
    return lane;
  }, [edges]);

  function edgeGeometry(
    s: { x: number; y: number; galaxy?: number },
    t: { x: number; y: number; galaxy?: number },
    side: number,
  ): {
    d: string;
    lx: number;
    ly: number;
    anchor: "start" | "middle" | "end";
  } {
    const dx = t.x - s.x;
    const dy = t.y - s.y;
    const len = Math.hypot(dx, dy) || 1;
    // Perpendicular unit (left of direction = negative side)
    const px = -dy / len;
    const py = dx / len;
    const pathOff = side * 7;
    const labelOff = side === 0 ? 0 : side * 16;
    const x1 = s.x + px * pathOff;
    const y1 = s.y + py * pathOff;
    const x2 = t.x + px * pathOff;
    const y2 = t.y + py * pathOff;
    const mx = (x1 + x2) / 2 + px * labelOff;
    const my = (y1 + y2) / 2 + py * labelOff;

    let d: string;
    if (classPrefix === "kg" && s.galaxy !== undefined && s.galaxy === t.galaxy) {
      const bend = Math.min(28, len * 0.18);
      const cx = (x1 + x2) / 2 - (dy / len) * bend;
      const cy = (y1 + y2) / 2 + (dx / len) * bend;
      d = `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`;
    } else {
      d = `M ${x1} ${y1} L ${x2} ${y2}`;
    }

    // Vertical-ish edges: side < 0 → label left (end), side > 0 → label right (start)
    const mostlyVertical = Math.abs(dy) >= Math.abs(dx);
    let anchor: "start" | "middle" | "end" = "middle";
    if (side < 0) anchor = mostlyVertical ? "end" : "middle";
    if (side > 0) anchor = mostlyVertical ? "start" : "middle";

    return { d, lx: mx, ly: my, anchor };
  }

  return (
    <svg
      className={`${classPrefix}-svg${panning ? " is-panning" : ""}`}
      viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      onPointerDown={onBgPointerDown}
      onPointerMove={onBgPointerMove}
      onPointerUp={onBgPointerUp}
      onPointerCancel={onBgPointerUp}
    >
      {classPrefix === "kg" ? (
        <defs>
          <radialGradient id="kgGalaxyGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(245, 158, 11, 0.22)" />
            <stop offset="55%" stopColor="rgba(180, 83, 9, 0.08)" />
            <stop offset="100%" stopColor="rgba(180, 83, 9, 0)" />
          </radialGradient>
        </defs>
      ) : null}
      {galaxyGuides.map((g) => (
        <g key={`galaxy-${g.gi}`} className="kg-galaxy" aria-hidden>
          <circle
            className="kg-galaxy-glow"
            cx={g.cx}
            cy={g.cy}
            r={g.glowR}
            fill="url(#kgGalaxyGlow)"
          />
          {g.rings.map((r, i) => (
            <ellipse
              key={`orbit-${g.gi}-${i}`}
              className="kg-orbit"
              cx={g.cx}
              cy={g.cy}
              rx={r}
              ry={r * 0.92}
            />
          ))}
          <text className="kg-galaxy-caption" x={g.cx} y={g.cy - g.glowR + 14} textAnchor="middle">
            {shortLabel(g.hubLabel, 18)}
          </text>
        </g>
      ))}
      {edges.map((e) => {
        const s = byId.get(e.source);
        const t = byId.get(e.target);
        if (!s || !t) return null;
        const side = edgeLane.get(e.id) ?? 0;
        const geo = edgeGeometry(s, t, side);
        const active = selectedEdgeId === e.id;
        const incidentToSelection =
          Boolean(selectedId) && (e.source === selectedId || e.target === selectedId);
        const bothEndsHi = highlighted.has(e.source) && highlighted.has(e.target);
        const hi =
          classPrefix === "kg"
            ? incidentToSelection
            : Boolean(selectedEdgeId === e.id) || bothEndsHi || incidentToSelection;
        const et = e.label || e.type || "";
        return (
          <g
            key={e.id}
            className={`${classPrefix}-edge-g ${active || hi ? "active" : ""}`}
            onClick={() => onEdgeClick?.(e.id)}
            style={{ cursor: onEdgeClick ? "pointer" : "default" }}
          >
            <path
              d={geo.d}
              className={`${classPrefix}-edge ${e.user_created ? "user" : ""} ${
                et === "CONTAINS" ? "spoke" : ""
              } ${et === "DEPENDS_ON" ? "depends" : ""} ${
                et === "CALLS" ? "calls" : ""
              } ${et === "USES" ? "uses" : ""} ${
                et === "INSTANCE_OF" ? "instance" : ""
              } ${et === "NEXT" ? "next" : ""} ${active || hi ? "lit" : ""}`}
            />
            {showEdgeLabels &&
            et &&
            et !== "CONTAINS" &&
            et !== "DEPENDS_ON" ? (
              <text
                x={geo.lx}
                y={geo.ly}
                textAnchor={geo.anchor}
                dominantBaseline="middle"
                className={`${classPrefix}-edge-label ${side < 0 ? "side-left" : ""} ${
                  side > 0 ? "side-right" : ""
                }`}
              >
                {et}
              </text>
            ) : null}
          </g>
        );
      })}
      {nodes.map((n) => {
        const isSelected = selectedId === n.id;
        const isHi = highlighted.has(n.id);
        const isFocus = isSelected || isHi || linkFrom === n.id;
        const isHub = Boolean(n.hub) && !n.isolate;
        let baseR =
          classPrefix === "lg"
            ? n.kind === "plc_ob"
              ? 20
              : 18
            : n.kind === "plc_project"
              ? 22
              : isHub
                ? 22
                : 15;
        if (n.isolate) baseR = 13;
        const maxChars = n.isolate ? 10 : isHub ? 18 : 16;
        const gt = resolveGraphType(n);
        return (
          <g
            key={n.id}
            data-kg-node={n.id}
            className={`${classPrefix}-node ${n.kind || n.type || ""} gt-${gt} ${
              n.isolate ? "isolate" : "galaxy"
            } ${isHub ? "hub" : ""} ${isSelected ? "selected" : ""} ${
              isHi ? "highlighted" : ""
            } ${linkFrom === n.id ? "linking" : ""}`}
            onPointerDown={(e) => {
              e.stopPropagation();
              onNodeDown(e, n.id);
            }}
            onPointerUp={(e) => onNodeUp(e, n.id)}
            style={{ cursor: dragId === n.id ? "grabbing" : "grab" }}
          >
            <title>{n.label}</title>
            {isHub ? (
              <circle className="kg-hub-halo" cx={n.x} cy={n.y} r={baseR + 10} />
            ) : null}
            <circle cx={n.x} cy={n.y} r={isFocus ? baseR + 4 : baseR} />
            <text
              x={n.x}
              y={n.y + (isFocus || isHub ? 34 : 28)}
              textAnchor="middle"
              fontWeight={isFocus || isHub ? 700 : undefined}
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
  knowledgeGraph,
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

  const laidOutKnowledge = useMemo(() => {
    // Display filter: PLC blocks/tags only (keeps project isolates; drops chat noise)
    const plc = data.nodes.filter(isPlcGraphNode);
    const ids = new Set(plc.map((n) => n.id));
    const edges = data.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
    // Re-layout so dropping dialogue nodes doesn't leave empty bottom strip gaps
    return autoLayoutKnowledge(plc, edges);
  }, [data.nodes, data.edges]);

  const byIdBase = useMemo(
    () => new Map(laidOutKnowledge.map((n) => [n.id, n])),
    [laidOutKnowledge],
  );
  const selectedBase = selectedId ? byIdBase.get(selectedId) : undefined;

  const signalOverlay = useMemo(
    () => buildSignalSubgraph(knowledgeGraph, selectedBase),
    [knowledgeGraph, selectedBase],
  );

  const displayKnowledge = useMemo(() => {
    if (!signalOverlay.nodes.length) return laidOutKnowledge;
    const ids = new Set(laidOutKnowledge.map((n) => n.id));
    return [...laidOutKnowledge, ...signalOverlay.nodes.filter((n) => !ids.has(n.id))];
  }, [laidOutKnowledge, signalOverlay.nodes]);

  const knowledgeEdges = useMemo(() => {
    const ids = new Set(displayKnowledge.map((n) => n.id));
    const base = data.edges.filter((e) => {
      if (!ids.has(e.source) || !ids.has(e.target)) return false;
      const label = e.label || "";
      if (e.user_created) return true;
      return (
        label === "CALLS" ||
        label === "USES" ||
        label === "INSTANCE_OF" ||
        label === "DEPENDS_ON"
      );
    });
    const sig = signalOverlay.edges.filter(
      (e) => ids.has(e.source) && ids.has(e.target),
    );
    return [...base, ...sig];
  }, [data.edges, displayKnowledge, signalOverlay.edges]);

  const logicLaid = useMemo(() => {
    if (!logicGraph) return { nodes: [], edges: [] };
    const hints = knowledgeEdges
      .filter((e) => {
        const lab = e.label || "";
        return lab === "CALLS" || lab === "USES" || lab === "INSTANCE_OF" || lab === "DEPENDS_ON";
      })
      .map((e) => {
        const sn = displayKnowledge.find((n) => n.id === e.source);
        const tn = displayKnowledge.find((n) => n.id === e.target);
        return {
          source: sn?.source?.block_name || sn?.label || e.source,
          target: tn?.source?.block_name || tn?.label || e.target,
          label: e.label,
        };
      });
    return logicLayout(logicGraph, hints);
  }, [logicGraph, knowledgeEdges, displayKnowledge]);

  const byId = useMemo(
    () => new Map(displayKnowledge.map((n) => [n.id, n])),
    [displayKnowledge],
  );
  const selected = selectedId ? byId.get(selectedId) : undefined;

  const knowledgeSize = useMemo(() => {
    const maxX = Math.max(640, ...displayKnowledge.map((n) => n.x + 80), 0);
    const maxY = Math.max(420, ...displayKnowledge.map((n) => n.y + 60), 0);
    return { w: maxX, h: maxY };
  }, [displayKnowledge]);

  const logicSize = useMemo(() => {
    const maxX = Math.max(640, ...logicLaid.nodes.map((n) => n.x + 80), 0);
    const maxY = Math.max(420, ...logicLaid.nodes.map((n) => n.y + 60), 0);
    return { w: maxX, h: maxY };
  }, [logicLaid.nodes]);

  const knowledgeLayoutKey = useMemo(
    () => displayKnowledge.map((n) => n.id).join("|") + `:${knowledgeEdges.length}`,
    [knowledgeEdges.length, displayKnowledge],
  );
  const logicLayoutKey = useMemo(
    () => logicLaid.nodes.map((n) => n.id).join("|") + `:${logicLaid.edges.length}`,
    [logicLaid.edges.length, logicLaid.nodes],
  );

  useEffect(() => {
    if (selectedId && !byId.has(selectedId) && !byIdBase.has(selectedId)) {
      setSelectedId(null);
    }
  }, [byId, byIdBase, selectedId]);

  // When selecting a block, auto-highlight its signal orbit
  useEffect(() => {
    if (!selectedBase || !signalOverlay.nodes.length) return;
    setHighlighted((prev) => {
      const next = new Set(prev);
      next.add(selectedBase.id);
      signalOverlay.nodes.forEach((n) => next.add(n.id));
      return next;
    });
  }, [selectedBase, signalOverlay.nodes]);

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
    // Signal overlay nodes are ephemeral — select only, don't drag into canvas state
    if (id.startsWith("sig_")) {
      e.stopPropagation();
      setSelectedId(id);
      setHighlighted(new Set([id, selectedBase?.id].filter(Boolean) as string[]));
      return;
    }
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

  /** Click focus: selected node + direct neighbors only (not whole galaxy). */
  function neighborFocusIds(seedId: string): Set<string> {
    const out = new Set<string>([seedId]);
    knowledgeEdges.forEach((e) => {
      if (e.source === seedId) out.add(e.target);
      if (e.target === seedId) out.add(e.source);
    });
    return out;
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
    const focus = neighborFocusIds(id);
    if (
      node.kind === "plc_block" ||
      node.kind === "plc_ob" ||
      node.kind === "plc_db" ||
      node.kind === "plc_udt" ||
      node.kind === "plc_instance"
    ) {
      const name = node.source?.block_name || node.label;
      const logicIds = logicLaid.nodes
        .filter(
          (ln) =>
            ln.label === name ||
            ln.label.replace(/^\d+\./, "") === name ||
            ln.id.endsWith(`::${name}`) ||
            ln.label.endsWith(`.${name}`),
        )
        .map((ln) => ln.id);
      if (logicIds[0]) setSelectedLogicId(logicIds[0]);
      setHighlighted(new Set([...focus, ...logicIds]));
      if (!busy && onNodeDescribe) void onNodeDescribe(node);
    } else {
      setHighlighted(focus);
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
    if (
      node &&
      (node.kind === "plc_block" ||
        node.kind === "plc_ob" ||
        node.kind === "plc_db" ||
        node.kind === "plc_udt" ||
        node.kind === "plc_instance") &&
      !busy &&
      onNodeDescribe
    ) {
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
    document.body.classList.add("col-resizing");
    const rect = host.getBoundingClientRect();
    const move = (ev: PointerEvent) => {
      const pct = ((ev.clientX - rect.left) / rect.width) * 100;
      setSplitPct(clampSplitPct(pct));
    };
    const up = (ev: PointerEvent) => {
      el.releasePointerCapture(ev.pointerId);
      document.body.classList.remove("col-resizing");
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
    const target =
      selected.id.startsWith("sig_") && selectedBase ? selectedBase : selected;
    await onDeepDive(target, q);
  }

  const hasSelection =
    Boolean(selectedId || selectedLogicId || selectedLogicEdge) || highlighted.size > 0;
  const logicCollapsed = splitPct <= 0;
  const knowledgeCollapsed = splitPct >= 100;

  return (
    <div className="kg-wrap">
      <div
        className={`kg-panes mode-both${hasSelection ? " has-selection" : ""}${
          logicCollapsed ? " logic-collapsed" : ""
        }${knowledgeCollapsed ? " knowledge-collapsed" : ""}`}
        ref={(el) => {
          svgHost.current = el;
          splitHost.current = el;
        }}
      >
        <div
          className={`kg-pane${logicCollapsed ? " is-collapsed" : ""}`}
          style={
            logicCollapsed
              ? { flex: "0 0 0px", width: 0, minWidth: 0 }
              : { flex: `0 0 ${splitPct}%`, width: `${splitPct}%` }
          }
          aria-hidden={logicCollapsed}
        >
          {logicLaid.nodes.length ? (
            <ZoomHost
              title="逻辑图"
              hint="滚轮缩放 · 拖动画布 · 查看全貌"
              layoutKey={logicLayoutKey}
              nodes={logicLaid.nodes}
              worldW={logicSize.w}
              worldH={logicSize.h}
            >
              {(z) => (
                <GraphPane
                  view={z.view}
                  nodes={logicLaid.nodes.map((n) => ({
                    ...n,
                    kind: n.kind || (n.type === "Block" ? "plc_block" : "plc_tag"),
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
                  panning={z.panning}
                  onNodeDown={() => undefined}
                  onNodeUp={onLogicNodeUp}
                  onEdgeClick={onLogicEdgeClick}
                  onBgPointerDown={z.onBgPointerDown}
                  onBgPointerMove={z.onBgPointerMove}
                  onBgPointerUp={z.onBgPointerUp}
                  classPrefix="lg"
                  showEdgeLabels={logicLaid.edges.length <= 30}
                />
              )}
            </ZoomHost>
          ) : (
            <>
              <div className="kg-pane-title">
                逻辑图
                <span className="kg-pane-hint">纵向扫描 · 互用块平行</span>
              </div>
              <div className="kg-scroll">
                <p className="empty kg-empty">暂无逻辑图</p>
              </div>
            </>
          )}
        </div>
        <div
          className={`kg-split${logicCollapsed ? " at-start" : ""}${
            knowledgeCollapsed ? " at-end" : ""
          }`}
          role="separator"
          aria-orientation="vertical"
          aria-valuenow={Math.round(splitPct)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="调整逻辑图与知识图谱宽度，拖到两端可完全隐藏一侧"
          title="拖动：0% 隐藏逻辑图 · 100% 隐藏知识图谱 · 双击恢复 50%"
          onPointerDown={onSplitPointerDown}
          onDoubleClick={() => setSplitPct(KG_SPLIT_DEFAULT)}
        />
        <div
          className={`kg-pane${knowledgeCollapsed ? " is-collapsed" : ""}`}
          style={
            knowledgeCollapsed
              ? { flex: "0 0 0px", width: 0, minWidth: 0 }
              : {
                  flex: logicCollapsed ? "1 1 auto" : `1 1 ${100 - splitPct}%`,
                  width: logicCollapsed ? "100%" : `${100 - splitPct}%`,
                }
          }
          aria-hidden={knowledgeCollapsed}
        >
          {displayKnowledge.length ? (
            <ZoomHost
              title="知识图谱"
              hint={
                signalOverlay.nodes.length
                  ? `已展开 ${signalOverlay.nodes.length} 个 IO/信号 · 滚轮缩放`
                  : "滚轮缩放 · 拖动画布 · 点块展开 IO"
              }
              layoutKey={knowledgeLayoutKey}
              nodes={displayKnowledge}
              worldW={knowledgeSize.w}
              worldH={knowledgeSize.h}
            >
              {(z) => (
                <GraphPane
                  view={z.view}
                  nodes={displayKnowledge}
                  edges={knowledgeEdges}
                  selectedId={selectedId}
                  highlighted={highlighted}
                  selectedEdgeId={null}
                  linkFrom={null}
                  dragId={dragId}
                  panning={z.panning}
                  onNodeDown={onKnowledgeDown}
                  onNodeUp={onKnowledgeUp}
                  onBgPointerDown={z.onBgPointerDown}
                  onBgPointerMove={(e) => {
                    z.onBgPointerMove(e);
                    onKnowledgeMove(e);
                  }}
                  onBgPointerUp={z.onBgPointerUp}
                  classPrefix="kg"
                  showEdgeLabels={knowledgeEdges.length <= 36}
                />
              )}
            </ZoomHost>
          ) : (
            <>
              <div className="kg-pane-title">
                知识图谱
                <span className="kg-pane-hint">星系 · 节点强制间距 · 孤立在底部</span>
              </div>
              <div className="kg-scroll">
                <p className="empty kg-empty">暂无知识图谱</p>
              </div>
            </>
          )}
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
          {signalOverlay.nodes.length && !selected.id.startsWith("sig_") ? (
            <p className="kg-summary muted">
              已展开 {signalOverlay.nodes.length} 个 IO/信号（READS/WRITES）
            </p>
          ) : null}
          <div className="kg-source">
            <div className="k">来源</div>
            <div className="v">
              {selected.source?.type || "dialogue"}
              {selected.source?.block_type ? ` · ${selected.source.block_type}` : ""}
              {selected.source?.instance_of
                ? ` · 实例←${selected.source.instance_of}`
                : selected.source?.entity_kind === "instance"
                  ? " · 实例 DB"
                  : ""}
              {selected.source?.project ? ` · ${selected.source.project}` : ""}
            </div>
            {selected.source?.path ? <pre className="kg-quote">{selected.source.path}</pre> : null}
            {selected.source?.quote ? <pre className="kg-quote">{selected.source.quote}</pre> : null}
          </div>
          <div className="kg-quick">
            <button
              type="button"
              className="ghost compact"
              disabled={busy}
              onClick={() => {
                if (!selected || busy) return;
                const target =
                  selected.id.startsWith("sig_") && selectedBase ? selectedBase : selected;
                void onDeepDive(target, "展开 SCL");
              }}
            >
              展开 SCL
            </button>
            <button
              type="button"
              className="ghost compact"
              disabled={busy}
              onClick={() => {
                if (!selected || busy) return;
                const target =
                  selected.id.startsWith("sig_") && selectedBase ? selectedBase : selected;
                void onDeepDive(target, "谁读写这些信号");
              }}
            >
              信号读写
            </button>
            <button
              type="button"
              className="ghost compact"
              disabled={busy}
              onClick={() => {
                if (!selected || busy) return;
                const target =
                  selected.id.startsWith("sig_") && selectedBase ? selectedBase : selected;
                void onDeepDive(target, "优化建议");
              }}
            >
              优化建议
            </button>
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
                const target =
                  selected.id.startsWith("sig_") && selectedBase ? selectedBase : selected;
                void onDeepDive(target, "请简述该块作用、关键 IO 与调用关系");
              }}
            >
              简述
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
