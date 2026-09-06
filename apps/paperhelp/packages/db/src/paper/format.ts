export const PAPER_EXTENSION = ".paper" as const;

export const PAPER_FORMAT_VERSION = "1.0" as const;

export const PAPER_FORMAT_ID = "paperhelp-paper" as const;

/** SQLite database file inside the .paper ZIP archive. */
export const PAPER_DB_FILE = "db.sqlite" as const;

/** Optional manifest with metadata. */
export const PAPER_MANIFEST_FILE = "manifest.json" as const;

/** Asset files directory inside the archive. */
export const PAPER_ASSETS_DIR = "assets" as const;

/** Figure preview PNG directory inside the archive. */
export const PAPER_PREVIEW_DIR = "preview" as const;

export interface PaperManifest {
  format: typeof PAPER_FORMAT_ID;
  version: typeof PAPER_FORMAT_VERSION;
  title: string;
  savedAt: number;
}

export function assetContainerPath(hash: string, ext: string): string {
  const normalizedExt = ext.startsWith(".") ? ext.slice(1) : ext;
  return `${PAPER_ASSETS_DIR}/${hash}.${normalizedExt}`;
}

export function previewContainerPath(figureId: string): string {
  return `${PAPER_PREVIEW_DIR}/${figureId}.png`;
}

export function extensionFromPath(path: string): string {
  const dot = path.lastIndexOf(".");
  if (dot === -1 || dot === path.length - 1) {
    return "bin";
  }
  return path.slice(dot + 1).toLowerCase();
}

export function defaultPaperFileName(title: string): string {
  const sanitized = title
    .trim()
    .replace(/[<>:"/\\|?*\x00-\x1f]/g, "")
    .replace(/\s+/g, " ")
    .slice(0, 80);
  const base = sanitized.length > 0 ? sanitized : "Untitled";
  return base.toLowerCase().endsWith(PAPER_EXTENSION)
    ? base
    : `${base}${PAPER_EXTENSION}`;
}

export function joinContainerPath(root: string, relativePath: string): string {
  const separator = root.includes("\\") ? "\\" : "/";
  const normalizedRoot = root.endsWith(separator) ? root.slice(0, -1) : root;
  const normalizedRelative = relativePath.replace(/\\/g, "/");
  return `${normalizedRoot}${separator}${normalizedRelative.replace(/\//g, separator)}`;
}
