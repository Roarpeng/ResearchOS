import JSZip from "jszip";
import { useAssetStore, useEditorStore, useFigureStore } from "@paperhelp/shared";
import { executeStatement, initDatabase, type SqliteDatabase } from "../client";
import {
  assetContainerPath,
  defaultPaperFileName,
  extensionFromPath,
  joinContainerPath,
  PAPER_ASSETS_DIR,
  PAPER_DB_FILE,
  PAPER_FORMAT_ID,
  PAPER_FORMAT_VERSION,
  PAPER_MANIFEST_FILE,
  PAPER_PREVIEW_DIR,
  previewContainerPath,
  type PaperManifest,
} from "./format";
import { syncStoresToDb } from "./sync";

export interface PaperFileIO {
  pickSavePath: (defaultName: string) => Promise<string | null>;
  pickOpenPath: () => Promise<string | null>;
  writeBinaryFile: (path: string, data: Uint8Array) => Promise<void>;
  readBinaryFile: (path: string) => Promise<Uint8Array>;
  copyFile: (src: string, dest: string) => Promise<void>;
  createTempDir: (prefix?: string) => Promise<string>;
  removePath: (path: string) => Promise<void>;
  listFiles?: (directory: string) => Promise<string[]>;
}

export interface SavePaperOptions {
  fileIO: PaperFileIO;
  savePath?: string;
  renderFigurePreview?: (
    figureId: string,
  ) => Promise<Uint8Array | null | undefined>;
}

async function exportDatabaseToPath(
  sqlite: SqliteDatabase,
  destinationPath: string,
): Promise<void> {
  const normalizedPath = destinationPath.replace(/\\/g, "/");
  await executeStatement(
    sqlite,
    `VACUUM INTO '${normalizedPath.replace(/'/g, "''")}'`,
  );
}

async function stageAssets(
  fileIO: PaperFileIO,
  stagingDir: string,
): Promise<void> {
  const assets = Object.values(useAssetStore.getState().assets);

  for (const asset of assets) {
    const ext = extensionFromPath(asset.path);
    const relativePath = assetContainerPath(asset.hash, ext);
    const destination = joinContainerPath(stagingDir, relativePath);
    await fileIO.copyFile(asset.path, destination);
  }
}

async function stageFigurePreviews(
  fileIO: PaperFileIO,
  stagingDir: string,
  renderFigurePreview?: SavePaperOptions["renderFigurePreview"],
): Promise<void> {
  if (!renderFigurePreview) {
    return;
  }

  const figures = useFigureStore.getState().figures;
  for (const figureId of Object.keys(figures)) {
    const preview = await renderFigurePreview(figureId);
    if (!preview || preview.length === 0) {
      continue;
    }

    const relativePath = previewContainerPath(figureId);
    const destination = joinContainerPath(stagingDir, relativePath);
    await fileIO.writeBinaryFile(destination, preview);
  }
}

async function zipStagingDirectory(
  stagingDir: string,
  fileIO: PaperFileIO,
): Promise<Uint8Array> {
  const zip = new JSZip();
  const dbPath = joinContainerPath(stagingDir, PAPER_DB_FILE);
  const dbBytes = await fileIO.readBinaryFile(dbPath);
  zip.file(PAPER_DB_FILE, dbBytes);

  const manifestPath = joinContainerPath(stagingDir, PAPER_MANIFEST_FILE);
  const manifestBytes = await fileIO.readBinaryFile(manifestPath);
  zip.file(PAPER_MANIFEST_FILE, manifestBytes);

  await addDirectoryToZip(
    zip,
    joinContainerPath(stagingDir, PAPER_ASSETS_DIR),
    PAPER_ASSETS_DIR,
    fileIO,
  );
  await addDirectoryToZip(
    zip,
    joinContainerPath(stagingDir, PAPER_PREVIEW_DIR),
    PAPER_PREVIEW_DIR,
    fileIO,
  );

  return zip.generateAsync({ type: "uint8array", compression: "DEFLATE" });
}

async function addDirectoryToZip(
  zip: JSZip,
  absoluteDir: string,
  zipPrefix: string,
  fileIO: PaperFileIO,
): Promise<void> {
  if (!fileIO.listFiles) {
    return;
  }

  let entries: string[] = [];
  try {
    entries = await fileIO.listFiles(absoluteDir);
  } catch {
    return;
  }

  for (const entry of entries) {
    const absolutePath = joinContainerPath(absoluteDir, entry);
    const zipPath = `${zipPrefix}/${entry}`;
    const bytes = await fileIO.readBinaryFile(absolutePath);
    zip.file(zipPath, bytes);
  }
}

export async function savePaper(options: SavePaperOptions): Promise<string | null> {
  const { fileIO, renderFigurePreview } = options;
  const title = useEditorStore.getState().title.trim() || "Untitled";
  const targetPath =
    options.savePath ??
    (await fileIO.pickSavePath(defaultPaperFileName(title)));

  if (!targetPath) {
    return null;
  }

  const stagingDir = await fileIO.createTempDir("paperhelp-save");
  const dbExportPath = joinContainerPath(stagingDir, PAPER_DB_FILE);

  try {
    const { sqlite } = await initDatabase();
    await syncStoresToDb(sqlite);
    await exportDatabaseToPath(sqlite, dbExportPath);

    await stageAssets(fileIO, stagingDir);
    await stageFigurePreviews(fileIO, stagingDir, renderFigurePreview);

    const manifest: PaperManifest = {
      format: PAPER_FORMAT_ID,
      version: PAPER_FORMAT_VERSION,
      title,
      savedAt: Date.now(),
    };
    const manifestPath = joinContainerPath(stagingDir, PAPER_MANIFEST_FILE);
    await fileIO.writeBinaryFile(
      manifestPath,
      new TextEncoder().encode(JSON.stringify(manifest, null, 2)),
    );

    const zipBytes = await zipStagingDirectory(stagingDir, fileIO);
    await fileIO.writeBinaryFile(targetPath, zipBytes);

    useEditorStore.getState().setDirty(false);
    useEditorStore.getState().setFilePath(targetPath);

    return targetPath;
  } finally {
    await fileIO.removePath(stagingDir);
  }
}
