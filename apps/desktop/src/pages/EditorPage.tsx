import { Editor } from "@paperhelp/editor";
import { useEditorStore, type ViewMode } from "@paperhelp/shared";
import { Button, Sidebar } from "@paperhelp/ui";
import { Outline } from "../components/Outline";

export function EditorPage() {
  const title = useEditorStore((s) => s.title);
  const setTitle = useEditorStore((s) => s.setTitle);
  const isDirty = useEditorStore((s) => s.isDirty);
  const viewMode = useEditorStore((s) => s.viewMode);
  const setViewMode = useEditorStore((s) => s.setViewMode);
  const sessionKey = useEditorStore((s) => s.sessionKey);

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
        </header>

        <div className="editor-page__editor">
          <Editor key={sessionKey} />
        </div>
      </section>

      <aside className="editor-page__figure-panel" aria-label="Figure properties">
        <div className="editor-page__figure-panel-header">Figure 属性</div>
        <p className="editor-page__figure-panel-placeholder">
          Sprint 2 将实现 Figure Studio 属性编辑。
        </p>
      </aside>
    </div>
  );
}
