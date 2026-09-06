import { invoke } from "@tauri-apps/api/core";
import { generateJSON } from "@tiptap/html";
import mammoth from "mammoth";
import { nanoid } from "nanoid";
import { useAssetStore, type Asset } from "@paperhelp/shared";
import { getExtensions } from "../extensions";
import type { ReadImageAssetResult } from "./types";

const MAX_DOCX_BYTES = 50 * 1024 * 1024;

interface ExtractedImage {
  contentType: string;
  buffer: ArrayBuffer;
}

export interface DocxImportResult {
  title: string;
  content: unknown;
  paragraphCount: number;
  imageCount: number;
}

function extensionFromMime(contentType: string): string {
  switch (contentType.toLowerCase()) {
    case "image/png":
      return "png";
    case "image/jpeg":
    case "image/jpg":
      return "jpg";
    case "image/gif":
      return "gif";
    case "image/webp":
      return "webp";
    case "image/tiff":
      return "tiff";
    default:
      return "png";
  }
}

function stripImageTags(html: string): string {
  return html
    .replace(/<img[^>]*\/>/gi, "")
    .replace(/<img[^>]*><\/img>/gi, "")
    .replace(/<img[^>]*>/gi, "");
}

function countTextBlocks(json: unknown): number {
  if (!json || typeof json !== "object") {
    return 0;
  }

  const doc = json as { content?: Array<{ type: string }> };
  if (!Array.isArray(doc.content)) {
    return 0;
  }

  return doc.content.filter((node) =>
    ["paragraph", "heading"].includes(node.type),
  ).length;
}

export function htmlToTiptapJson(html: string): unknown {
  const trimmed = stripImageTags(html).trim();
  if (!trimmed) {
    return {
      type: "doc",
      content: [{ type: "paragraph" }],
    };
  }

  return generateJSON(trimmed, getExtensions());
}

async function parseDocxBuffer(buffer: ArrayBuffer): Promise<{
  html: string;
  images: ExtractedImage[];
  warnings: string[];
}> {
  const images: ExtractedImage[] = [];

  const result = await mammoth.convertToHtml(
    { arrayBuffer: buffer },
    {
      convertImage: mammoth.images.imgElement(async (image) => {
        const imageBuffer = await image.read();
        images.push({
          contentType: image.contentType,
          buffer: imageBuffer.buffer.slice(
            imageBuffer.byteOffset,
            imageBuffer.byteOffset + imageBuffer.byteLength,
          ),
        });
        return { src: "" };
      }),
    },
  );

  return {
    html: stripImageTags(result.value),
    images,
    warnings: result.messages.map((message) => message.message),
  };
}

async function registerDocxImage(image: ExtractedImage): Promise<Asset> {
  const extension = extensionFromMime(image.contentType);
  const data = Array.from(new Uint8Array(image.buffer));

  const result = await invoke<ReadImageAssetResult>("read_image_from_bytes", {
    data,
    extension,
  });

  const store = useAssetStore.getState();
  const existing = store.getAssetByHash(result.hash);
  if (existing) {
    if (!store.getThumbnail(result.hash)) {
      store.cacheThumbnail(result.hash, result.thumbnail);
    }
    return existing;
  }

  const asset: Asset = {
    id: nanoid(),
    path: result.path,
    hash: result.hash,
    width: result.width,
    height: result.height,
    mime: result.mime,
  };

  store.addAsset(asset, result.thumbnail);
  return asset;
}

export async function importDocxDocument(): Promise<DocxImportResult | null> {
  const path = await invoke<string | null>("pick_docx_file");
  if (!path) {
    return null;
  }

  const raw = await invoke<number[]>("read_binary_file", { path });
  const buffer = new Uint8Array(raw).buffer;

  if (buffer.byteLength === 0) {
    throw new Error("文档为空或无法读取");
  }

  if (buffer.byteLength > MAX_DOCX_BYTES) {
    throw new Error("文档过大（超过 50MB），请拆分后重试");
  }

  const filename = path.split(/[/\\]/).pop() ?? "Untitled.docx";
  const title = filename.replace(/\.docx$/i, "") || "未命名文档";

  const { html, images } = await parseDocxBuffer(buffer);
  const content = htmlToTiptapJson(html);
  const paragraphCount = countTextBlocks(content);

  let imageCount = 0;
  for (const image of images) {
    await registerDocxImage(image);
    imageCount += 1;
  }

  if (paragraphCount === 0 && imageCount === 0) {
    throw new Error("文档不包含可导入的文字或图片");
  }

  return {
    title,
    content,
    paragraphCount,
    imageCount,
  };
}
