import { useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Editor } from "@paperhelp/editor";
import {
  UpdateDocumentTitleCommand,
  useCommandHistoryStore,
  useEditorStore,
  type ViewMode,
} from "@paperhelp/shared";
import { Button, Sidebar } from "@paperhelp/ui";
import { FigurePropertiesPanel } from "../components/FigurePropertiesPanel";
import { Outline } from "../components/Outline";
import {
  usePaperDocument,
  usePaperKeyboardShortcuts,
} from "../hooks/usePaperDocument";
import { insertFigureIntoEditor } from "../utils/insertFigureIntoEditor";

export function EditorPage() {
  const navigate = useNavigate();
  const title = useEditorStore((s) => s.title);
  const isDirty = useEditorStore((s) => s.isDirty);
  const canUndo = useCommandHistoryStore((s) => s.canUndo);
  const canRedo = useCommandHistoryStore((s) => s.canRedo);
  const executeCommand = useCommandHistoryStore((s) => s.execute);
  const undoCommand = useCommandHistoryStore((s) => s.undo);
  const redoCommand = useCommandHistoryStore((s) => s.redo);
  const viewMode = useEditorStore((s) => s.viewMode);
  const setViewMode = useEditorStore((s) => s.setViewMode);
  const sessionKey = useEditorStore((s) => s.sessionKey);
  const selectedFigureId = useEditorStore((s) => s.selectedFigureId);
  const editorCommands = useEditorStore((s) => s.editorCommands);
  const {
    busy: paperBusy,
    message: paperMessage,
    handleSave,
    handleSaveAs,
    handleOpen,
  } = usePaperDocument();

  usePaperKeyboardShortcuts(() => {
    void handleSave();
  });

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "z") {
        return;
      }

      const target = event.target;
      if (target instanceof HTMLElement && target.closest(".ProseMirror")) {
        return;
      }

      event.preventDefault();
      if (event.shiftKey) {
        redoCommand();
      } else {
        undoCommand();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [redoCommand, undoCommand]);

  const handleTitleChange = useCallback(
    (nextTitle: string) => {
      const prevTitle = useEditorStore.getState().title;
      if (prevTitle === nextTitle) {
        return;
      }

      executeCommand(new UpdateDocumentTitleCommand(prevTitle, nextTitle));
    },
    [executeCommand],
  );

  const handleOpenFigure = useCallback(
    (figureId: string) => {
      navigate(`/figure/${figureId}`);
    },
    [navigate],
  );

  const handleInsertFigure = useCallback(() => {
    insertFigureIntoEditor(editorCommands);
  }, [editorCommands]);

  return (
    <div className="editor-page">
      <Sidebar title="大纲" className="editor-page__outline">
        <Outline />
      </Sidebar>

      <section className="editor-page__main">
        <header className="editor-page__toolbar">
          <div className="editor-page__title">
            <input
              id="doc-title"
              className="doc-title-input"
              value={title}
              onChange={(e) => handleTitleChange(e.currentTarget.value)}
              placeholder="Untitled"
              aria-label="Document title"
            />
            {isDirty ? <span className="dirty-indicator">Unsaved</span> : null}
          </div>

          <div className="editor-page__toolbar-actions">
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={!canUndo}
              onClick={undoCommand}
              aria-label="Undo"
            >
              撤销
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={!canRedo}
              onClick={redoCommand}
              aria-label="Redo"
            >
              重做
            </Button>

            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={paperBusy || !editorCommands}
              onClick={() => void handleSave()}
            >
              保存
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={paperBusy || !editorCommands}
              onClick={() => void handleSaveAs()}
            >
              另存为
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={paperBusy}
              onClick={() => void handleOpen()}
            >
              打开
            </Button>

            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={!editorCommands}
              onClick={handleInsertFigure}
            >
              插入 Figure
            </Button>

            <div
              className="view-mode-toggle"
              role="group"
              aria-label="Editor view mode"
            >
              {(
                [
                  { mode: "scroll" as ViewMode, label: "Scroll" },
                  { mode: "a4" as ViewMode, label: "A4" },
                ] as const
              ).map(({ mode, label }) => (
                <Button
                  key={mode}
                  type="button"
                  size="sm"
                  variant={viewMode === mode ? "secondary" : "outline"}
                  aria-pressed={viewMode === mode}
                  onClick={() => setViewMode(mode)}
                >
                  {label}
                </Button>
              ))}
            </div>
          </div>
        </header>

        {paperMessage ? (
          <p className="editor-page__status" role="status">
            {paperMessage}
          </p>
        ) : null}

        <div className="editor-page__editor">
          <Editor key={sessionKey} onOpenFigure={handleOpenFigure} />
        </div>
      </section>

      {selectedFigureId ? (
        <FigurePropertiesPanel
          figureId={selectedFigureId}
          className="editor-page__figure-panel"
        />
      ) : (
        <aside className="editor-page__figure-panel" aria-label="Figure properties">
          <div className="editor-page__figure-panel-header">Figure 属性</div>
          <p className="editor-page__figure-panel-placeholder">
            在文档中选中 Figure 块以编辑标题、自动排版等属性；双击 Figure 块可在 Figure Studio 中打开。
          </p>
        </aside>
      )}
    </div>
  );
}
