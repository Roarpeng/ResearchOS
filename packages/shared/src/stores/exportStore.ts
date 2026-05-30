import { create } from "zustand";

export type ExportFormat = "pdf" | "docx" | "markdown";

/** Export workflow state — full pipeline deferred to Sprint 4 */
export interface ExportState {
  format: ExportFormat | null;
  isExporting: boolean;
  lastExportPath: string | null;
}

export interface ExportActions {
  setFormat: (format: ExportFormat | null) => void;
  setExporting: (isExporting: boolean) => void;
  setLastExportPath: (path: string | null) => void;
  reset: () => void;
}

export type ExportStore = ExportState & ExportActions;

const initialExportState: ExportState = {
  format: null,
  isExporting: false,
  lastExportPath: null,
};

export const useExportStore = create<ExportStore>((set) => ({
  ...initialExportState,
  setFormat: (format) => set({ format }),
  setExporting: (isExporting) => set({ isExporting }),
  setLastExportPath: (lastExportPath) => set({ lastExportPath }),
  reset: () => set(initialExportState),
}));
