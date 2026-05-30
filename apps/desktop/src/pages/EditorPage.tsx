import { useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Editor } from "@paperhelp/editor";
import {
  useCommandHistoryStore,
  useEditorStore,
  type ViewMode,
} from "@paperhelp/shared";
import { Button } from "@paperhelp/ui";
import { AssetLibraryPanel } from "../components/AssetLibraryPanel";
import { DocumentControlsPanel } from "../components/DocumentControlsPanel";
import {
  usePaperDocument,
  usePaperKeyboardShortcuts,
} from "../hooks/usePaperDocument";
import { useExportPdf } from "../hooks/useExportPdf";
import { insertFigureIntoEditor } from "../utils/insertFigureIntoEditor";

export function EditorPage() {
  const navigate = useNavigate();
  const saveStatus = useEditorStore((s) => s.saveStatus);
  const canUndo = useCommandHistoryStore((s) => s.canUndo);
  const canRedo = useCommandHistoryStore((s) => s.canRedo);
  const undoCommand = useCommandHistoryStore((s) => s.undo);
  const redoCommand = useCommandHistoryStore((s) => s.redo);
  const viewMode = useEditorStore((s) => s.viewMode);
  const setViewMode = useEditorStore((s) => s.setViewMode);
  const sessionKey = useEditorStore((s) => s.sessionKey);
  const editorCommands = useEditorStore((s) => s.editorCommands);
  const {
    busy: paperBusy,
    message: paperMessage,
    handleSave,
    handleSaveAs,
    handleOpen,
  } = usePaperDocument();

  const {
    handleExportPdf,
    handleExportSubmissionPack,
    isExporting,
    progress: exportProgress,
    lastExportPath,
    exportFormat,
    error: exportError,
  } = useExportPdf();

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
      <aside className="editor-page__outline" aria-label="Document controls">
        <div className="editor-page__outline-header">文档</div>
        <DocumentControlsPanel />
      </aside>

      <section className="editor-page__main">
        <header className="editor-page__toolbar">
          <div className="editor-page__title">
            <span
              className={`editor-page__save-status editor-page__save-status--${saveStatus}`}
              role="status"
            >
              {saveStatus === "saved"
                ? "已保存"
                : saveStatus === "saving"
                  ? "保存中…"
                  : "未保存"}
            </span>
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

            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={!editorCommands || isExporting || paperBusy}
              onClick={() => void handleExportPdf()}
            >
              {isExporting && exportFormat === "pdf"
                ? `导出 PDF ${exportProgress}%`
                : "导出 PDF"}
            </Button>

            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={!editorCommands || isExporting || paperBusy}
              onClick={() => void handleExportSubmissionPack()}
            >
              {isExporting && exportFormat === "zip"
                ? `导出投稿包 ${exportProgress}%`
                : "导出投稿包"}
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

        {exportError ? (
          <p className="editor-page__status editor-page__status--error" role="alert">
            导出失败：{exportError}
          </p>
        ) : null}

        {lastExportPath && !isExporting && !exportError ? (
          <p className="editor-page__status editor-page__status--success" role="status">
            {exportFormat === "zip"
              ? `已导出投稿包到 ${lastExportPath}`
              : `已导出 PDF 到 ${lastExportPath}`}
          </p>
        ) : null}

        <div className="editor-page__editor">
          <Editor key={sessionKey} onOpenFigure={handleOpenFigure} />
        </div>
      </section>

      <AssetLibraryPanel
        className="editor-page__asset-panel"
        editorCommands={editorCommands}
      />
    </div>
  );
}
