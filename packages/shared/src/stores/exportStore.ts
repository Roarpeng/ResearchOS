import { create } from "zustand";

export type ExportFormat = "pdf" | "zip" | "docx" | "markdown";

/** Export workflow state */
export interface ExportState {
  format: ExportFormat | null;
  isExporting: boolean;
  progress: number;
  lastExportPath: string | null;
  error: string | null;
}

export interface ExportActions {
  setFormat: (format: ExportFormat | null) => void;
  setExporting: (isExporting: boolean) => void;
  setProgress: (progress: number) => void;
  setLastExportPath: (path: string | null) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export type ExportStore = ExportState & ExportActions;

const initialExportState: ExportState = {
  format: null,
  isExporting: false,
  progress: 0,
  lastExportPath: null,
  error: null,
};

export const useExportStore = create<ExportStore>((set) => ({
  ...initialExportState,
  setFormat: (format) => set({ format }),
  setExporting: (isExporting) => set({ isExporting }),
  setProgress: (progress) => set({ progress }),
  setLastExportPath: (lastExportPath) => set({ lastExportPath }),
  setError: (error) => set({ error }),
  reset: () => set(initialExportState),
}));
