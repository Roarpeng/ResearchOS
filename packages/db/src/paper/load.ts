import JSZip from "jszip";
import { useEditorStore } from "@paperhelp/shared";
import { closeDatabase, initDatabase } from "../client";
import {
  joinContainerPath,
  PAPER_ASSETS_DIR,
  PAPER_DB_FILE,
  PAPER_MANIFEST_FILE,
  PAPER_PREVIEW_DIR,
} from "./format";
import { hydrateStoresFromDb, type SyncContext } from "./sync";
import type { PaperFileIO } from "./save";

export interface LoadPaperOptions {
  fileIO: PaperFileIO;
  openPath?: string;
  syncContext: SyncContext;
}

async function extractZipToDirectory(
  zipBytes: Uint8Array,
  destinationDir: string,
  fileIO: PaperFileIO,
): Promise<void> {
  const zip = await JSZip.loadAsync(zipBytes);
  const entries = Object.values(zip.files).filter((entry) => !entry.dir);

  for (const entry of entries) {
    const normalizedName = entry.name.replace(/\\/g, "/");
    const destination = joinContainerPath(destinationDir, normalizedName);
    const bytes = await entry.async("uint8array");
    await fileIO.writeBinaryFile(destination, bytes);
  }
}

export async function loadPaper(
  options: LoadPaperOptions,
): Promise<{ documentId: string; title: string; filePath: string } | null> {
  const { fileIO, syncContext } = options;
  const sourcePath = options.openPath ?? (await fileIO.pickOpenPath());

  if (!sourcePath) {
    return null;
  }

  const extractDir = await fileIO.createTempDir("paperhelp-load");

  try {
    const zipBytes = await fileIO.readBinaryFile(sourcePath);
    await extractZipToDirectory(zipBytes, extractDir, fileIO);

    const dbPath = joinContainerPath(extractDir, PAPER_DB_FILE);
    await closeDatabase();
    const { sqlite } = await initDatabase(`sqlite:${dbPath}`, { force: true });
    const loaded = await hydrateStoresFromDb(sqlite, extractDir, syncContext);

    useEditorStore.getState().setFilePath(sourcePath);
    useEditorStore.getState().setContainerRoot(extractDir);

    return {
      documentId: loaded.documentId,
      title: loaded.title,
      filePath: sourcePath,
    };
  } catch (error) {
    await fileIO.removePath(extractDir);
    throw error;
  }
}

export function isPaperArchiveEntry(name: string): boolean {
  const normalized = name.replace(/\\/g, "/");
  return (
    normalized === PAPER_DB_FILE ||
    normalized === PAPER_MANIFEST_FILE ||
    normalized.startsWith(`${PAPER_ASSETS_DIR}/`) ||
    normalized.startsWith(`${PAPER_PREVIEW_DIR}/`)
  );
}
