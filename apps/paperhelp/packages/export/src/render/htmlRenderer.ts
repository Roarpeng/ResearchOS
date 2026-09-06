import type { Figure } from "@paperhelp/shared";
import { buildPrintCss, PRINT_CSS } from "./printCss";

interface TiptapMark {
  type: string;
  attrs?: Record<string, unknown>;
}

interface TiptapNode {
  type: string;
  attrs?: Record<string, unknown>;
  content?: TiptapNode[];
  text?: string;
  marks?: TiptapMark[];
}

export interface HtmlRenderContext {
  title: string;
  documentJson: unknown;
  figures: Record<string, Figure>;
  figureImages: Record<string, string>;
  fontFamilyCss: string;
  fontSizePt: number;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderMarks(text: string, marks?: TiptapMark[]): string {
  if (!marks?.length) {
    return escapeHtml(text);
  }

  let result = escapeHtml(text);
  for (const mark of marks) {
    switch (mark.type) {
      case "bold":
        result = `<strong>${result}</strong>`;
        break;
      case "italic":
        result = `<em>${result}</em>`;
        break;
      case "strike":
        result = `<s>${result}</s>`;
        break;
      case "code":
        result = `<code>${result}</code>`;
        break;
      case "link": {
        const href = String(mark.attrs?.href ?? "#");
        result = `<a href="${escapeHtml(href)}">${result}</a>`;
        break;
      }
      default:
        break;
    }
  }

  return result;
}

function renderChildren(node: TiptapNode, ctx: HtmlRenderContext): string {
  return node.content?.map((child) => renderNode(child, ctx)).join("") ?? "";
}

function renderFigureNode(node: TiptapNode, ctx: HtmlRenderContext): string {
  const figureId = node.attrs?.figureId as string | null | undefined;
  if (!figureId) {
    return '<figure class="figure-block figure-block--missing"><p>Missing figure reference</p></figure>';
  }

  const figure = ctx.figures[figureId];
  const title = figure?.title ?? "Figure";
  const imgSrc = ctx.figureImages[figureId];

  if (imgSrc) {
    return `<figure class="figure-block">
  <img src="${imgSrc}" alt="${escapeHtml(title)}" />
  <figcaption>${escapeHtml(title)}</figcaption>
</figure>`;
  }

  return `<figure class="figure-block figure-block--empty">
  <figcaption>${escapeHtml(title)}</figcaption>
</figure>`;
}

function renderNode(node: TiptapNode, ctx: HtmlRenderContext): string {
  switch (node.type) {
    case "doc":
      return renderChildren(node, ctx);
    case "paragraph":
      return `<p>${renderChildren(node, ctx)}</p>`;
    case "heading": {
      const level = Number(node.attrs?.level ?? 1);
      const tag = level >= 1 && level <= 6 ? `h${level}` : "h1";
      return `<${tag}>${renderChildren(node, ctx)}</${tag}>`;
    }
    case "text":
      return renderMarks(node.text ?? "", node.marks);
    case "hardBreak":
      return "<br />";
    case "bulletList":
      return `<ul>${renderChildren(node, ctx)}</ul>`;
    case "orderedList":
      return `<ol>${renderChildren(node, ctx)}</ol>`;
    case "listItem":
      return `<li>${renderChildren(node, ctx)}</li>`;
    case "blockquote":
      return `<blockquote>${renderChildren(node, ctx)}</blockquote>`;
    case "codeBlock":
      return `<pre><code>${renderChildren(node, ctx)}</code></pre>`;
    case "horizontalRule":
      return "<hr />";
    case "table":
      return `<table>${renderChildren(node, ctx)}</table>`;
    case "tableRow":
      return `<tr>${renderChildren(node, ctx)}</tr>`;
    case "tableHeader":
      return `<th>${renderChildren(node, ctx)}</th>`;
    case "tableCell":
      return `<td>${renderChildren(node, ctx)}</td>`;
    case "figure":
      return renderFigureNode(node, ctx);
    case "citation":
      return '<div class="citation-block">[Citation placeholder]</div>';
    default:
      return renderChildren(node, ctx);
  }
}

/** Collect figure node ids referenced in a Tiptap document JSON tree. */
export function collectFigureIds(documentJson: unknown): string[] {
  const ids = new Set<string>();

  const walk = (node: unknown) => {
    if (!node || typeof node !== "object") {
      return;
    }

    const record = node as TiptapNode;
    if (record.type === "figure" && record.attrs?.figureId) {
      ids.add(String(record.attrs.figureId));
    }

    record.content?.forEach(walk);
  };

  walk(documentJson);
  return [...ids];
}

/** Render a full HTML document suitable for Puppeteer PDF export. */
export function renderDocumentHtml(ctx: HtmlRenderContext): string {
  const root = ctx.documentJson as TiptapNode | null;
  const body = root ? renderNode(root, ctx) : "";
  const title = escapeHtml(ctx.title || "Untitled");
  const titleBlock = ctx.title
    ? `<h1 class="document-title">${title}</h1>`
    : "";
  const printCss = buildPrintCss({
    fontFamilyCss: ctx.fontFamilyCss,
    fontSizePt: ctx.fontSizePt,
  });

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>${title}</title>
  <style>${printCss}</style>
</head>
<body>
  ${titleBlock}
  ${body}
</body>
</html>`;
}

export { PRINT_CSS };
