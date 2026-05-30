import { useCallback } from "react";
import {
  exportFigureToPng,
  renderFigureThumbnailToDataUrl,
} from "@paperhelp/figure";
import {
  ExportCancelledError,
  ExportEngine,
} from "@paperhelp/export";
import {
  useAssetStore,
  useEditorStore,
  useExportStore,
  useFigureStore,
  type Asset,
} from "@paperhelp/shared";
import {
  exportFileIO,
  exportPdfHtml,
  pickExportPdfPath,
} from "../services/exportIo";
import { assetPathToDataUrl } from "../services/assetImage";

const exportEngine = new ExportEngine({
  pickPdfSavePath: pickExportPdfPath,
  pickZipSavePath: exportFileIO.pickZipSavePath,
  exportPdf: exportPdfHtml,
  createTempDir: exportFileIO.createTempDir,
  removePath: exportFileIO.removePath,
  readBinaryFile: exportFileIO.readBinaryFile,
  writeBinaryFile: exportFileIO.writeBinaryFile,
});

function buildDocumentExportState() {
  const editorCommands = useEditorStore.getState().editorCommands;
  if (!editorCommands) {
    return null;
  }

  return {
    title: useEditorStore.getState().title,
    figures: useFigureStore.getState().figures,
    documentJson: editorCommands.getJSON(),
    getFigureImageDataUrl: async (figureId: string) => {
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
  };
}

function buildFigurePngExporter() {
  const resolveAsset = (assetId: string) => useAssetStore.getState().assets[assetId];
  const getAssetImageDataUrl = async (asset: Asset) => assetPathToDataUrl(asset);

  return (figure: Parameters<typeof exportFigureToPng>[0]) =>
    exportFigureToPng(figure, resolveAsset, getAssetImageDataUrl, { pixelRatio: 2 });
}

export function useExportPdf() {
  const isExporting = useExportStore((state) => state.isExporting);
  const progress = useExportStore((state) => state.progress);
  const lastExportPath = useExportStore((state) => state.lastExportPath);
  const exportFormat = useExportStore((state) => state.format);
  const error = useExportStore((state) => state.error);

  const runExport = useCallback(
    async (format: "pdf" | "zip", exportFn: () => Promise<string>) => {
      const {
        setExporting,
        setProgress,
        setLastExportPath,
        setError,
        setFormat,
      } = useExportStore.getState();

      setFormat(format);
      setExporting(true);
      setProgress(0);
      setError(null);

      try {
        const outputPath = await exportFn();
        setLastExportPath(outputPath);
        return outputPath;
      } catch (exportError) {
        if (exportError instanceof ExportCancelledError) {
          return null;
        }

        const message =
          exportError instanceof Error
            ? exportError.message
            : format === "pdf"
              ? "PDF 导出失败"
              : "投稿包导出失败";
        setError(message);
        return null;
      } finally {
        useExportStore.getState().setExporting(false);
      }
    },
    [],
  );

  const handleExportPdf = useCallback(async () => {
    const state = buildDocumentExportState();
    if (!state) {
      useExportStore.getState().setError("编辑器尚未就绪");
      return null;
    }

    return runExport("pdf", () =>
      exportEngine.exportPdf(state, useExportStore.getState().setProgress),
    );
  }, [runExport]);

  const handleExportSubmissionPack = useCallback(async () => {
    const state = buildDocumentExportState();
    if (!state) {
      useExportStore.getState().setError("编辑器尚未就绪");
      return null;
    }

    return runExport("zip", () =>
      exportEngine.exportSubmissionPack(
        state,
        buildFigurePngExporter(),
        useExportStore.getState().setProgress,
      ),
    );
  }, [runExport]);

  return {
    handleExportPdf,
    handleExportSubmissionPack,
    isExporting,
    progress,
    lastExportPath,
    exportFormat,
    error,
  };
}
