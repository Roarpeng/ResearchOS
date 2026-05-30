import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Editor } from "@paperhelp/editor";
import { useEditorStore, type ViewMode } from "@paperhelp/shared";
import { Button, Sidebar } from "@paperhelp/ui";
import { FigurePropertiesPanel } from "../components/FigurePropertiesPanel";
import { Outline } from "../components/Outline";
import { insertFigureIntoEditor } from "../utils/insertFigureIntoEditor";

export function EditorPage() {
  const navigate = useNavigate();
  const title = useEditorStore((s) => s.title);
  const setTitle = useEditorStore((s) => s.setTitle);
  const isDirty = useEditorStore((s) => s.isDirty);
  const viewMode = useEditorStore((s) => s.viewMode);
  const setViewMode = useEditorStore((s) => s.setViewMode);
  const sessionKey = useEditorStore((s) => s.sessionKey);
  const selectedFigureId = useEditorStore((s) => s.selectedFigureId);
  const setDirty = useEditorStore((s) => s.setDirty);
  const editorCommands = useEditorStore((s) => s.editorCommands);

  const handleOpenFigure = useCallback(
    (figureId: string) => {
      navigate(`/figure/${figureId}`);
    },
    [navigate],
  );

  const handleInsertFigure = useCallback(() => {
    insertFigureIntoEditor(editorCommands);
  }, [editorCommands]);

  const handleFigureChange = useCallback(() => {
    setDirty(true);
  }, [setDirty]);

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
              onChange={(e) => setTitle(e.currentTarget.value)}
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

        <div className="editor-page__editor">
          <Editor key={sessionKey} onOpenFigure={handleOpenFigure} />
        </div>
      </section>

      {selectedFigureId ? (
        <FigurePropertiesPanel
          figureId={selectedFigureId}
          className="editor-page__figure-panel"
          onFigureChange={handleFigureChange}
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
