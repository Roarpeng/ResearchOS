import type { PlcCitation } from "../api";
import type { KnowledgeNode } from "../KnowledgeCanvas";

export type Topic = {
  id: string;
  title: string;
  status: string;
  route?: string;
  plcJobId?: string | null;
};

export type ChatScope = {
  nodeId: string;
  blockName: string;
  label: string;
  kind: string;
  looksLikeOutput?: boolean;
  nestDepth?: number;
};

export const ROLE_CHIPS = ["工艺主控", "设备驱动", "厂商库", "可拆辅助", "不要动"] as const;
export const NESTED_CHIPS = ["必须的多实例", "意外耦合"] as const;

export type ChatMsg = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  at: number;
  citations?: PlcCitation[];
  /** Node-scoped user turns render a small `@FB_Motor` prefix. */
  scopeLabel?: string;
};

const PLC_SCOPE_KINDS = new Set([
  "plc_block",
  "plc_ob",
  "plc_db",
  "plc_udt",
  "plc_instance",
  "plc_tag",
]);

export function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function looksLikeOutputCoil(node: KnowledgeNode): boolean {
  const label = String(node.label || "");
  const summary = String(node.summary || "");
  const quote = String(node.source?.quote || "");
  const blob = `${label} ${summary} ${quote}`;
  if (/WRITE/i.test(summary)) return true;
  if (/^(Q|%Q|Y)\b/i.test(label)) return true;
  return /%Q|线圈|coil|output|输出/i.test(blob);
}

export function isPlcScopeNode(node: KnowledgeNode | null | undefined): boolean {
  if (!node) return false;
  if (PLC_SCOPE_KINDS.has(String(node.kind || ""))) return true;
  return Boolean(node.source?.type === "plc" && (node.source.block_name || node.source.quote));
}

export function chatScopeFromNode(node: KnowledgeNode): ChatScope {
  const blockName =
    String(node.source?.block_name || "").trim() ||
    (node.kind === "plc_tag" ? String(node.label || "").trim() : "") ||
    String(node.label || "").trim();
  return {
    nodeId: node.id,
    blockName,
    label: String(node.label || blockName || node.id),
    kind: String(node.kind || ""),
    looksLikeOutput: looksLikeOutputCoil(node),
    nestDepth: Number(node.source?.nest_depth || 0) || 0,
  };
}

export function mentionFromText(text: string): string | null {
  const hit = text.match(/^@(\S+)/);
  return hit?.[1] || null;
}

export function userBubbleParts(m: ChatMsg): { prefix?: string; body: string } {
  if (m.scopeLabel) {
    const re = new RegExp(`^@${escapeRegExp(m.scopeLabel)}\\s*`);
    return { prefix: m.scopeLabel, body: m.content.replace(re, "") || m.content };
  }
  const hit = m.content.match(/^@(\S+)\s+([\s\S]+)$/);
  if (hit) return { prefix: hit[1], body: hit[2] };
  return { body: m.content };
}

export function attachCitationNodes(citations: PlcCitation[] | undefined, nodes: KnowledgeNode[]): PlcCitation[] {
  if (!citations?.length) return [];
  return citations.map((c) => {
    if (c.nodeId) return c;
    const block = String(c.block || "").trim();
    const target = String(c.target || "").trim();
    const hit =
      nodes.find((n) => n.id === block || n.source?.block_name === block || n.label === block) ||
      nodes.find((n) => n.id === target || n.source?.block_name === target || n.label === target);
    return hit ? { ...c, nodeId: hit.id } : c;
  });
}

export function titleFromQuery(q: string): string {
  const t = q.trim().replace(/\s+/g, " ");
  return t.length > 42 ? `${t.slice(0, 40)}…` : t || "未命名话题";
}

export function pretty(value: unknown): string {
  if (value == null || value === "") return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}
