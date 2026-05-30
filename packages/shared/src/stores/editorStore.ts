import { create } from "zustand";

export type ViewMode = "scroll" | "a4";

export interface EditorState {
  documentId: string | null;
  title: string;
  viewMode: ViewMode;
  isDirty: boolean;
}

export interface EditorActions {
  setDocumentId: (documentId: string | null) => void;
  setTitle: (title: string) => void;
  setViewMode: (viewMode: ViewMode) => void;
  setDirty: (isDirty: boolean) => void;
  reset: () => void;
}

export type EditorStore = EditorState & EditorActions;

const initialEditorState: EditorState = {
  documentId: null,
  title: "",
  viewMode: "scroll",
  isDirty: false,
};

export const useEditorStore = create<EditorStore>((set) => ({
  ...initialEditorState,
  setDocumentId: (documentId) => set({ documentId }),
  setTitle: (title) => set({ title }),
  setViewMode: (viewMode) => set({ viewMode }),
  setDirty: (isDirty) => set({ isDirty }),
  reset: () => set(initialEditorState),
}));
