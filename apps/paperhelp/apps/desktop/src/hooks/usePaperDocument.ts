import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  initDatabase,
  loadPaper,
  persistHistoryEntry,
  savePaper,
  type SyncContext,
} from "@paperhelp/db";
import { renderFigureThumbnailToDataUrl } from "@paperhelp/figure";
import {
  useAssetStore,
  useCommandHistoryStore,
  useEditorStore,
  useFigureStore,
} from "@paperhelp/shared";
import {
  dataUrlToUint8Array,
  paperFileIO,
  readImageAssetForPaper,
} from "../services/paperIo";

export function usePaperDocument() {
  const navigate = useNavigate();
  const filePath = useEditorStore((state) => state.filePath);
  const title = useEditorStore((state) => state.title);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const syncContext = useMemo<SyncContext>(
    () => ({
      getEditorJSON: () => {
        const commands = useEditorStore.getState().editorCommands;
        if (!commands) {
          throw new Error("Editor is not ready");
        }
        return commands.getJSON();
      },
      setEditorJSON: (json) => {
        useEditorStore.getState().setDocumentContent(json);
        const commands = useEditorStore.getState().editorCommands;
        commands?.setContent(json);
      },
      readImageAsset: readImageAssetForPaper,
    }),
    [],
  );

  useEffect(() => {
    void initDatabase();
  }, []);

  useEffect(() => {
    useCommandHistoryStore.getState().setPersist((action, payload) => {
      void persistHistoryEntry(action, payload).catch((error) => {
        console.error("Failed to persist command history", error);
      });
    });

    return () => {
      useCommandHistoryStore.getState().setPersist(undefined);
    };
  }, []);

  const renderFigurePreview = useCallback(async (figureId: string) => {
    const figure = useFigureStore.getState().figures[figureId];
    if (!figure) {
      return null;
    }

    const dataUrl = await renderFigureThumbnailToDataUrl(
      figure,
      (assetId) => useAssetStore.getState().assets[assetId],
      (hash) => useAssetStore.getState().getThumbnail(hash),
    );

    return dataUrl ? dataUrlToUint8Array(dataUrl) : null;
  }, []);

  const handleSave = useCallback(
    async (explicitPath?: string) => {
      if (!useEditorStore.getState().editorCommands) {
        setMessage("编辑器尚未就绪");
        return null;
      }

      setBusy(true);
      setMessage(null);

      try {
        const savedPath = await savePaper({
          fileIO: paperFileIO,
          savePath: explicitPath ?? filePath ?? undefined,
          renderFigurePreview,
        });

        if (savedPath) {
          setMessage(`已保存到 ${savedPath}`);
        }

        return savedPath;
      } catch (error) {
        const text = error instanceof Error ? error.message : "保存失败";
        setMessage(text);
        return null;
      } finally {
        setBusy(false);
      }
    },
    [filePath, renderFigurePreview],
  );

  const handleOpen = useCallback(async () => {
    setBusy(true);
    setMessage(null);

    try {
      const loaded = await loadPaper({
        fileIO: paperFileIO,
        syncContext,
      });

      if (!loaded) {
        return null;
      }

      navigate(`/editor/${loaded.documentId}`);
      setMessage(`已打开 ${loaded.title}`);
      return loaded;
    } catch (error) {
      const text = error instanceof Error ? error.message : "打开失败";
      setMessage(text);
      return null;
    } finally {
      setBusy(false);
    }
  }, [navigate, syncContext]);

  const handleSaveAs = useCallback(async () => {
    return handleSave(undefined);
  }, [handleSave]);

  return {
    busy,
    message,
    filePath,
    title,
    handleSave,
    handleSaveAs,
    handleOpen,
    clearMessage: () => setMessage(null),
  };
}

export function usePaperKeyboardShortcuts(
  onSave: () => void | Promise<void>,
  enabled = true,
) {
  useEffect(() => {
    if (!enabled) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "s") {
        return;
      }

      event.preventDefault();
      void onSave();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [enabled, onSave]);
}
