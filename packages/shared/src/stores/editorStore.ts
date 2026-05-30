import { create } from "zustand";

export type ViewMode = "scroll" | "a4";

export interface OutlineItem {
  id: string;
  level: 1 | 2 | 3;
  text: string;
}

export interface EditorCommands {
  focus: () => void;
  toggleHeading: (level: 1 | 2 | 3) => void;
}

export interface EditorState {
  documentId: string | null;
  title: string;
  viewMode: ViewMode;
  isDirty: boolean;
  outline: OutlineItem[];
  sessionKey: number;
  editorCommands: EditorCommands | null;
}

export interface EditorActions {
  setDocumentId: (documentId: string | null) => void;
  setTitle: (title: string) => void;
  setViewMode: (viewMode: ViewMode) => void;
  setDirty: (isDirty: boolean) => void;
  setOutline: (outline: OutlineItem[]) => void;
  setEditorCommands: (commands: EditorCommands | null) => void;
  reset: () => void;
}

export type EditorStore = EditorState & EditorActions;

const initialEditorState: EditorState = {
  documentId: null,
  title: "",
  viewMode: "scroll",
  isDirty: false,
  outline: [],
  sessionKey: 0,
  editorCommands: null,
};

export const useEditorStore = create<EditorStore>((set) => ({
  ...initialEditorState,
  setDocumentId: (documentId) => set({ documentId }),
  setTitle: (title) => set({ title }),
  setViewMode: (viewMode) => set({ viewMode }),
  setDirty: (isDirty) => set({ isDirty }),
  setOutline: (outline) => set({ outline }),
  setEditorCommands: (editorCommands) => set({ editorCommands }),
  reset: () =>
    set((state) => ({
      ...initialEditorState,
      sessionKey: state.sessionKey + 1,
    })),
}));
