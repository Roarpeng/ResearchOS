import { useCallback } from "react";
import {
  ExportCancelledError,
  ExportEngine,
} from "@paperhelp/export";
import { renderFigureThumbnailToDataUrl } from "@paperhelp/figure";
import {
  useAssetStore,
  useEditorStore,
  useExportStore,
  useFigureStore,
} from "@paperhelp/shared";
import { exportPdfHtml, pickExportPdfPath } from "../services/exportIo";

const exportEngine = new ExportEngine({
  pickPdfSavePath: pickExportPdfPath,
  exportPdf: exportPdfHtml,
});

export function useExportPdf() {
  const isExporting = useExportStore((state) => state.isExporting);
  const progress = useExportStore((state) => state.progress);
  const lastExportPath = useExportStore((state) => state.lastExportPath);
  const error = useExportStore((state) => state.error);

  const handleExportPdf = useCallback(async () => {
    const editorCommands = useEditorStore.getState().editorCommands;
    if (!editorCommands) {
      useExportStore.getState().setError("编辑器尚未就绪");
      return null;
    }

    const {
      setExporting,
      setProgress,
      setLastExportPath,
      setError,
      setFormat,
    } = useExportStore.getState();

    setFormat("pdf");
    setExporting(true);
    setProgress(0);
    setError(null);

    try {
      const title = useEditorStore.getState().title;
      const figures = useFigureStore.getState().figures;
      const documentJson = editorCommands.getJSON();

      const outputPath = await exportEngine.exportPdf(
        {
          title,
          documentJson,
          figures,
          getFigureImageDataUrl: async (figureId) => {
            const figure = useFigureStore.getState().figures[figureId];
            if (!figure) {
              return null;
            }

            return renderFigureThumbnailToDataUrl(
              figure,
              (assetId) => useAssetStore.getState().assets[assetId],
              (hash) => useAssetStore.getState().getThumbnail(hash),
              { width: 640, height: 400 },
            );
          },
        },
        setProgress,
      );

      setLastExportPath(outputPath);
      return outputPath;
    } catch (exportError) {
      if (exportError instanceof ExportCancelledError) {
        return null;
      }

      const message =
        exportError instanceof Error ? exportError.message : "PDF 导出失败";
      setError(message);
      return null;
    } finally {
      useExportStore.getState().setExporting(false);
    }
  }, []);

  return {
    handleExportPdf,
    isExporting,
    progress,
    lastExportPath,
    error,
  };
}
