import type { Figure } from "@paperhelp/shared";
import {
  collectFigureIds,
  renderDocumentHtml,
  type HtmlRenderContext,
} from "./render/htmlRenderer";

export interface DocumentExportState {
  title: string;
  documentJson: unknown;
  figures: Record<string, Figure>;
  getFigureImageDataUrl: (figureId: string) => Promise<string | null>;
}

export interface ExportBackend {
  pickPdfSavePath: (defaultName: string) => Promise<string | null>;
  exportPdf: (html: string, outputPath: string) => Promise<void>;
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
