import { joinContainerPath } from "../paper/format";
import { useEditorStore } from "@paperhelp/shared";
import { loadPaper, type LoadPaperOptions } from "../paper/load";
import type { PaperFileIO } from "../paper/save";

export const AUTOSAVE_DIR_NAME = "autosave";
export const RECOVERY_MARKER_FILE = ".paper-recovery";
export const RECOVERY_PAPER_FILE = "recovery.paper";

export interface RecoveryMarker {
  sessionActive: boolean;
  recoveryPaperPath: string;
  originalFilePath: string | null;
  title: string;
  documentId: string | null;
  updatedAt: number;
}

export interface RecoveryPaths {
  autosaveDir: string;
  markerPath: string;
  recoveryPaperPath: string;
}

export function getRecoveryPaths(appDataDir: string): RecoveryPaths {
  const autosaveDir = joinContainerPath(appDataDir, AUTOSAVE_DIR_NAME);
  return {
    autosaveDir,
    markerPath: joinContainerPath(autosaveDir, RECOVERY_MARKER_FILE),
    recoveryPaperPath: joinContainerPath(autosaveDir, RECOVERY_PAPER_FILE),
  };
}

async function readTextFile(
  fileIO: PaperFileIO,
  path: string,
): Promise<string | null> {
  try {
    const bytes = await fileIO.readBinaryFile(path);
    return new TextDecoder().decode(bytes);
  } catch {
    return null;
  }
}

async function writeTextFile(
  fileIO: PaperFileIO,
  path: string,
  text: string,
): Promise<void> {
  await fileIO.writeBinaryFile(path, new TextEncoder().encode(text));
}

export async function writeRecoveryMarker(
  fileIO: PaperFileIO,
  paths: RecoveryPaths,
  marker: RecoveryMarker,
): Promise<void> {
  await writeTextFile(
    fileIO,
    paths.markerPath,
    JSON.stringify(marker, null, 2),
  );
}

export async function readRecoveryMarker(
  fileIO: PaperFileIO,
  paths: RecoveryPaths,
): Promise<RecoveryMarker | null> {
  const raw = await readTextFile(fileIO, paths.markerPath);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as RecoveryMarker;
  } catch {
    return null;
  }
}

export async function clearRecoverySession(
  fileIO: PaperFileIO,
  paths: RecoveryPaths,
): Promise<void> {
  const marker = await readRecoveryMarker(fileIO, paths);
  if (marker) {
    await writeRecoveryMarker(fileIO, paths, {
      ...marker,
      sessionActive: false,
      updatedAt: Date.now(),
    });
  }
}

export async function removeRecoveryArtifacts(
  fileIO: PaperFileIO,
  paths: RecoveryPaths,
): Promise<void> {
  await fileIO.removePath(paths.markerPath);
  await fileIO.removePath(paths.recoveryPaperPath);
}

export async function checkRecoveryAvailable(
  fileIO: PaperFileIO,
  appDataDir: string,
): Promise<RecoveryMarker | null> {
  const paths = getRecoveryPaths(appDataDir);
  const marker = await readRecoveryMarker(fileIO, paths);

  if (!marker?.sessionActive) {
    return null;
  }

  try {
    await fileIO.readBinaryFile(marker.recoveryPaperPath);
    return marker;
  } catch {
    return null;
  }
}

export async function recoverPaperFromMarker(
  options: LoadPaperOptions & { marker: RecoveryMarker },
): Promise<{ documentId: string; title: string; filePath: string } | null> {
  const loaded = await loadPaper({
    ...options,
    openPath: options.marker.recoveryPaperPath,
  });

  if (!loaded) {
    return null;
  }

  if (options.marker.originalFilePath) {
    useEditorStore.getState().setFilePath(options.marker.originalFilePath);
  }

  return loaded;
}

export async function updateRecoveryMarkerAfterSave(
  fileIO: PaperFileIO,
  paths: RecoveryPaths,
  details: {
    originalFilePath: string | null;
    title: string;
    documentId: string | null;
  },
): Promise<void> {
  const marker: RecoveryMarker = {
    sessionActive: true,
    recoveryPaperPath: paths.recoveryPaperPath,
    originalFilePath: details.originalFilePath,
    title: details.title,
    documentId: details.documentId,
    updatedAt: Date.now(),
  };
  await writeRecoveryMarker(fileIO, paths, marker);
}
