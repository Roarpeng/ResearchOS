import { create } from "zustand";
import type { DocumentFontFamily, DocumentFontSize } from "../types/typography";

export type ViewMode = "scroll" | "a4";

export type SaveStatus = "saved" | "saving" | "unsaved";

export interface OutlineItem {
  id: string;
  level: 1 | 2 | 3;
  text: string;
}

export interface EditorCommands {
  focus: () => void;
  toggleHeading: (level: 1 | 2 | 3) => void;
  insertFigure: (figureId: string) => void;
  getJSON: () => unknown;
  setContent: (json: unknown) => void;
}

export interface EditorState {
  documentId: string | null;
  title: string;
  fontFamily: DocumentFontFamily;
  fontSize: DocumentFontSize;
  viewMode: ViewMode;
  isDirty: boolean;
  saveStatus: SaveStatus;
  /** Increments on each edit for autosave debounce scheduling. */
  editRevision: number;
  outline: OutlineItem[];
  sessionKey: number;
  editorCommands: EditorCommands | null;
  selectedFigureId: string | null;
  /** Loaded Tiptap JSON applied on the next editor mount. */
  documentContent: unknown | null;
  /** Current .paper file path on disk, when saved or opened. */
  filePath: string | null;
  /** Extracted container directory for opened .paper assets. */
  containerRoot: string | null;
}

export interface EditorActions {
  setDocumentId: (documentId: string | null) => void;
  setTitle: (title: string) => void;
  setFontFamily: (fontFamily: DocumentFontFamily) => void;
  setFontSize: (fontSize: DocumentFontSize) => void;
  setViewMode: (viewMode: ViewMode) => void;
  setDirty: (isDirty: boolean) => void;
  setSaveStatus: (saveStatus: SaveStatus) => void;
  setOutline: (outline: OutlineItem[]) => void;
  setEditorCommands: (commands: EditorCommands | null) => void;
  setSelectedFigureId: (figureId: string | null) => void;
  setDocumentContent: (documentContent: unknown | null) => void;
  setFilePath: (filePath: string | null) => void;
  setContainerRoot: (containerRoot: string | null) => void;
  reset: () => void;
}

export type EditorStore = EditorState & EditorActions;

const initialEditorState: EditorState = {
  documentId: null,
  title: "",
  fontFamily: "times",
  fontSize: 12,
  viewMode: "scroll",
  isDirty: false,
  saveStatus: "saved",
  editRevision: 0,
  outline: [],
  sessionKey: 0,
  editorCommands: null,
  selectedFigureId: null,
  documentContent: null,
  filePath: null,
  containerRoot: null,
};

export const useEditorStore = create<EditorStore>((set) => ({
  ...initialEditorState,
  setDocumentId: (documentId) => set({ documentId }),
  setTitle: (title) => set({ title }),
  setFontFamily: (fontFamily) => set({ fontFamily }),
  setFontSize: (fontSize) => set({ fontSize }),
  setViewMode: (viewMode) => set({ viewMode }),
  setDirty: (isDirty) =>
    set((state) => ({
      isDirty,
      ...(isDirty
        ? {
            editRevision: state.editRevision + 1,
            saveStatus: "unsaved" as SaveStatus,
          }
        : {}),
    })),
  setSaveStatus: (saveStatus) => set({ saveStatus }),
  setOutline: (outline) => set({ outline }),
  setEditorCommands: (editorCommands) => set({ editorCommands }),
  setSelectedFigureId: (selectedFigureId) => set({ selectedFigureId }),
  setDocumentContent: (documentContent) => set({ documentContent }),
  setFilePath: (filePath) => set({ filePath }),
  setContainerRoot: (containerRoot) => set({ containerRoot }),
  reset: () =>
    set((state) => ({
      ...initialEditorState,
      sessionKey: state.sessionKey + 1,
    })),
}));
