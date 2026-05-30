import { createContext, useContext, type ReactNode } from "react";

export interface EditorContextValue {
  onOpenFigure?: (figureId: string) => void;
}

const EditorContext = createContext<EditorContextValue>({});

export function EditorProvider({
  children,
  onOpenFigure,
}: EditorContextValue & { children: ReactNode }) {
  return (
    <EditorContext.Provider value={{ onOpenFigure }}>{children}</EditorContext.Provider>
  );
}

export function useEditorContext(): EditorContextValue {
  return useContext(EditorContext);
}
