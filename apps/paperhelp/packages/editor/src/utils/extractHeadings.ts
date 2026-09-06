import type { JSONContent } from "@tiptap/core";

export interface OutlineItem {
  id: string;
  level: 1 | 2 | 3;
  text: string;
}

function extractText(node: JSONContent): string {
  if (node.text) {
    return node.text;
  }
  if (!node.content) {
    return "";
  }
  return node.content.map(extractText).join("");
}

export function extractHeadings(doc: JSONContent): OutlineItem[] {
  const items: OutlineItem[] = [];
  let index = 0;

  function walk(node: JSONContent) {
    if (
      node.type === "heading" &&
      typeof node.attrs?.level === "number" &&
      node.attrs.level >= 1 &&
      node.attrs.level <= 3
    ) {
      const text = extractText(node).trim();
      items.push({
        id: `heading-${index++}`,
        level: node.attrs.level as 1 | 2 | 3,
        text: text || "Untitled heading",
      });
    }

    node.content?.forEach(walk);
  }

  walk(doc);
  return items;
}
