import type { Figure } from "@paperhelp/shared";
import {
  collectFigureIds,
  renderDocumentHtml,
  type HtmlRenderContext,
} from "./render/htmlRenderer";
import {
  buildSubmissionPackZip,
  type SubmissionPackMetadata,
} from "./zip/submissionPack";

export interface DocumentExportState {
  title: string;
  documentJson: unknown;
  figures: Record<string, Figure>;
  getFigureImageDataUrl: (figureId: string) => Promise<string | null>;
}

export interface ExportBackend {
  pickPdfSavePath: (defaultName: string) => Promise<string | null>;
  pickZipSavePath: (defaultName: string) => Promise<string | null>;
  exportPdf: (html: string, outputPath: string) => Promise<void>;
  createTempDir: (prefix: string) => Promise<string>;
  removePath: (path: string) => Promise<void>;
  readBinaryFile: (path: string) => Promise<Uint8Array>;
  writeBinaryFile: (path: string, data: Uint8Array) => Promise<void>;
}

export type ExportProgressCallback = (progress: number) => void;

export class ExportEngine {
  constructor(private readonly backend: ExportBackend) {}

  /** Build HTML from document state without writing a PDF. */
  async buildHtml(state: DocumentExportState): Promise<string> {
    const figureImages = await this.resolveFigureImages(state);
    return renderDocumentHtml({
      title: state.title,
      documentJson: state.documentJson,
      figures: state.figures,
      figureImages,
    });
  }

  /**
   * Export the current document to PDF.
   * Prompts for save path via backend, renders HTML, then invokes Puppeteer.
   */
  async exportPdf(
    state: DocumentExportState,
    onProgress?: ExportProgressCallback,
  ): Promise<string> {
    onProgress?.(5);

    const defaultName = `${sanitizeFilename(state.title || "Untitled")}.pdf`;
    const outputPath = await this.backend.pickPdfSavePath(defaultName);
    if (!outputPath) {
      throw new ExportCancelledError();
    }

    onProgress?.(15);

    const figureImages = await this.resolveFigureImages(state);
    onProgress?.(45);

    const html = renderDocumentHtml({
      title: state.title,
      documentJson: state.documentJson,
      figures: state.figures,
      figureImages,
    });
    onProgress?.(60);

    await this.backend.exportPdf(html, outputPath);
    onProgress?.(100);

    return outputPath;
  }

  /**
   * Export manuscript PDF plus high-resolution figure PNGs as a submission ZIP.
   */
  async exportSubmissionPack(
    state: DocumentExportState,
    exportFigurePng: (figure: Figure) => Promise<Uint8Array | null>,
    onProgress?: ExportProgressCallback,
  ): Promise<string> {
    onProgress?.(5);

    const defaultName = `${sanitizeFilename(state.title || "Untitled")}.zip`;
    const outputPath = await this.backend.pickZipSavePath(defaultName);
    if (!outputPath) {
      throw new ExportCancelledError();
    }

    onProgress?.(10);

    const tempDir = await this.backend.createTempDir("paperhelp-submission");
    try {
      const figureImages = await this.resolveFigureImages(state);
      onProgress?.(25);

      const html = renderDocumentHtml({
        title: state.title,
        documentJson: state.documentJson,
        figures: state.figures,
        figureImages,
      });

      const pdfPath = joinPath(tempDir, "manuscript.pdf");
      await this.backend.exportPdf(html, pdfPath);
      onProgress?.(50);

      const pdfBytes = await this.backend.readBinaryFile(pdfPath);
      const figureList = Object.values(state.figures);
      const figureEntries: { filename: string; pngBytes: Uint8Array }[] = [];

      for (let index = 0; index < figureList.length; index += 1) {
        const figure = figureList[index];
        const pngBytes = await exportFigurePng(figure);
        if (pngBytes) {
          figureEntries.push({
            filename: `figure-${index + 1}.png`,
            pngBytes,
          });
        }

        const figureProgress = figureList.length
          ? 50 + Math.floor(((index + 1) / figureList.length) * 35)
          : 85;
        onProgress?.(figureProgress);
      }

      const metadata: SubmissionPackMetadata = {
        title: state.title,
        authors: [],
        exportedAt: new Date().toISOString(),
        figureCount: figureEntries.length,
      };

      const zipBytes = await buildSubmissionPackZip({
        pdfBytes,
        figures: figureEntries,
        metadata,
      });
      onProgress?.(95);

      await this.backend.writeBinaryFile(outputPath, zipBytes);
      onProgress?.(100);

      return outputPath;
    } finally {
      await this.backend.removePath(tempDir);
    }
  }

  private async resolveFigureImages(
    state: DocumentExportState,
  ): Promise<Record<string, string>> {
    const figureIds = collectFigureIds(state.documentJson);
    const figureImages: Record<string, string> = {};

    await Promise.all(
      figureIds.map(async (figureId) => {
        const dataUrl = await state.getFigureImageDataUrl(figureId);
        if (dataUrl) {
          figureImages[figureId] = dataUrl;
        }
      }),
    );

    return figureImages;
  }
}

export class ExportCancelledError extends Error {
  constructor() {
    super("Export cancelled");
    this.name = "ExportCancelledError";
  }
}

export type { HtmlRenderContext };
export { collectFigureIds, renderDocumentHtml };

function sanitizeFilename(name: string): string {
  return name.replace(/[<>:"/\\|?*\u0000-\u001f]/g, "_").trim() || "Untitled";
}

function joinPath(base: string, segment: string): string {
  const separator = base.includes("\\") ? "\\" : "/";
  return base.endsWith(separator) ? `${base}${segment}` : `${base}${separator}${segment}`;
}
