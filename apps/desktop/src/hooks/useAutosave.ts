import { useEffect, useRef } from "react";
import { renderFigureThumbnailToDataUrl } from "@paperhelp/figure";
import {
  registerSyncContext,
  startAutosaveScheduler,
  type AutosaveController,
  type SyncContext,
} from "@paperhelp/db";
import {
  useAssetStore,
  useEditorStore,
  useFigureStore,
} from "@paperhelp/shared";
import {
  dataUrlToUint8Array,
  getAppDataDir,
  paperFileIO,
} from "../services/paperIo";
import { finalizeSessionOnClose } from "./useRecovery";

export function useAutosave(syncContext: SyncContext) {
  const controllerRef = useRef<AutosaveController | null>(null);

  useEffect(() => {
    registerSyncContext(syncContext);
  }, [syncContext]);

  useEffect(() => {
    const renderFigurePreview = async (figureId: string) => {
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
    };

    const controller = startAutosaveScheduler({
      fileIO: paperFileIO,
      getAppDataDir,
      renderFigurePreview,
    });
    controllerRef.current = controller;

    return () => {
      controller.stop();
      controllerRef.current = null;
    };
  }, []);

  useEffect(() => {
    let unlistenClose: (() => void) | undefined;

    void (async () => {
      try {
        const { getCurrentWindow } = await import("@tauri-apps/api/window");
        unlistenClose = await getCurrentWindow().onCloseRequested(async (event) => {
          event.preventDefault();
          await finalizeSessionOnClose(async () => {
            await controllerRef.current?.flush();
          });
          await getCurrentWindow().destroy();
        });
      } catch {
        // Non-Tauri environments fall back to beforeunload.
      }
    })();

    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!useEditorStore.getState().isDirty) {
        return;
      }

      void finalizeSessionOnClose(async () => {
        await controllerRef.current?.flush();
      });
      event.preventDefault();
    };

    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      unlistenClose?.();
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, []);
}
