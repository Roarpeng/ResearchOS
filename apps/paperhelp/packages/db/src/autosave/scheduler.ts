import { useEditorStore } from "@paperhelp/shared";
import {
  getRecoveryPaths,
  updateRecoveryMarkerAfterSave,
  type RecoveryPaths,
} from "./recovery";
import { savePaper, type PaperFileIO, type SavePaperOptions } from "../paper/save";

const DEFAULT_DEBOUNCE_MS = 30_000;

export interface AutosaveSchedulerOptions {
  fileIO: PaperFileIO;
  getAppDataDir: () => Promise<string>;
  debounceMs?: number;
  renderFigurePreview?: SavePaperOptions["renderFigurePreview"];
}

export interface AutosaveController {
  stop: () => void;
  flush: () => Promise<void>;
}

function canAutosave(): boolean {
  const { editorCommands, isDirty } = useEditorStore.getState();
  return Boolean(editorCommands && isDirty);
}

async function performAutosave(
  fileIO: PaperFileIO,
  paths: RecoveryPaths,
  renderFigurePreview?: SavePaperOptions["renderFigurePreview"],
): Promise<boolean> {
  if (!canAutosave()) {
    return false;
  }

  const editorState = useEditorStore.getState();
  useEditorStore.getState().setSaveStatus("saving");

  try {
    const savedPath = await savePaper({
      fileIO,
      savePath: paths.recoveryPaperPath,
      updateDocumentState: false,
      renderFigurePreview,
    });

    if (!savedPath) {
      useEditorStore.getState().setSaveStatus("unsaved");
      return false;
    }

    await updateRecoveryMarkerAfterSave(fileIO, paths, {
      originalFilePath: editorState.filePath,
      title: editorState.title,
      documentId: editorState.documentId,
    });

    useEditorStore.getState().setSaveStatus(
      editorState.isDirty ? "unsaved" : "saved",
    );
    return true;
  } catch (error) {
    console.error("Autosave failed", error);
    useEditorStore.getState().setSaveStatus("unsaved");
    return false;
  }
}

export function startAutosaveScheduler(
  options: AutosaveSchedulerOptions,
): AutosaveController {
  const debounceMs = options.debounceMs ?? DEFAULT_DEBOUNCE_MS;
  let debounceTimer: ReturnType<typeof setTimeout> | null = null;
  let pathsPromise: Promise<RecoveryPaths> | null = null;
  let stopped = false;

  const resolvePaths = async (): Promise<RecoveryPaths> => {
    if (!pathsPromise) {
      pathsPromise = options.getAppDataDir().then(getRecoveryPaths);
    }
    return pathsPromise;
  };

  const cancelScheduledSave = () => {
    if (debounceTimer) {
      clearTimeout(debounceTimer);
      debounceTimer = null;
    }
  };

  const scheduleAutosave = () => {
    if (stopped || !useEditorStore.getState().isDirty) {
      return;
    }

    cancelScheduledSave();
    debounceTimer = setTimeout(() => {
      debounceTimer = null;
      void (async () => {
        const paths = await resolvePaths();
        await performAutosave(
          options.fileIO,
          paths,
          options.renderFigurePreview,
        );
      })();
    }, debounceMs);
  };

  const flush = async () => {
    cancelScheduledSave();
    if (!canAutosave()) {
      return;
    }

    const paths = await resolvePaths();
    await performAutosave(
      options.fileIO,
      paths,
      options.renderFigurePreview,
    );
  };

  const unsubscribe = useEditorStore.subscribe((state, previousState) => {
    if (state.editRevision !== previousState.editRevision && state.isDirty) {
      scheduleAutosave();
    }

    if (!state.isDirty && previousState.isDirty) {
      cancelScheduledSave();
    }
  });

  return {
    stop: () => {
      stopped = true;
      cancelScheduledSave();
      unsubscribe();
    },
    flush,
  };
}
