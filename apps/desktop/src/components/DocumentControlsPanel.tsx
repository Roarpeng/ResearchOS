import { useCallback } from "react";
import {
  DOCUMENT_FONT_OPTIONS,
  DOCUMENT_FONT_SIZE_OPTIONS,
  UpdateDocumentTitleCommand,
  useCommandHistoryStore,
  useEditorStore,
  type DocumentFontFamily,
  type DocumentFontSize,
} from "@paperhelp/shared";
import { Outline } from "./Outline";

export function DocumentControlsPanel() {
  const title = useEditorStore((s) => s.title);
  const fontFamily = useEditorStore((s) => s.fontFamily);
  const fontSize = useEditorStore((s) => s.fontSize);
  const saveStatus = useEditorStore((s) => s.saveStatus);
  const setFontFamily = useEditorStore((s) => s.setFontFamily);
  const setFontSize = useEditorStore((s) => s.setFontSize);
  const executeCommand = useCommandHistoryStore((s) => s.execute);

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

  return (
    <div className="document-controls">
      <section className="document-controls__section" aria-label="Document settings">
        <label className="document-controls__field" htmlFor="doc-title-sidebar">
          <span className="document-controls__label">文档标题</span>
          <input
            id="doc-title-sidebar"
            className="document-controls__input"
            value={title}
            onChange={(e) => handleTitleChange(e.currentTarget.value)}
            placeholder="Untitled"
          />
        </label>

        <span
          className={`document-controls__save-status document-controls__save-status--${saveStatus}`}
          role="status"
        >
          {saveStatus === "saved"
            ? "已保存"
            : saveStatus === "saving"
              ? "保存中…"
              : "未保存"}
        </span>

        <label className="document-controls__field" htmlFor="doc-font-family">
          <span className="document-controls__label">正文字体</span>
          <select
            id="doc-font-family"
            className="document-controls__select"
            value={fontFamily}
            onChange={(e) =>
              setFontFamily(e.currentTarget.value as DocumentFontFamily)
            }
          >
            {DOCUMENT_FONT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="document-controls__field" htmlFor="doc-font-size">
          <span className="document-controls__label">正文字号</span>
          <select
            id="doc-font-size"
            className="document-controls__select"
            value={fontSize}
            onChange={(e) =>
              setFontSize(Number(e.currentTarget.value) as DocumentFontSize)
            }
          >
            {DOCUMENT_FONT_SIZE_OPTIONS.map((size) => (
              <option key={size} value={size}>
                {size} pt
              </option>
            ))}
          </select>
        </label>
      </section>

      <section className="document-controls__section" aria-label="Document outline">
        <h2 className="document-controls__section-title">大纲</h2>
        <Outline />
      </section>
    </div>
  );
}
