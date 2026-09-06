import { useCallback } from "react";
import { NodeViewWrapper } from "@tiptap/react";
import type { NodeViewProps } from "@tiptap/react";
import { FigureThumbnailPreview } from "@paperhelp/figure";
import { useFigureStore } from "@paperhelp/shared";
import { useEditorContext } from "../context/EditorContext";

export function FigureBlockView({ node, selected }: NodeViewProps) {
  const figureId = node.attrs.figureId as string | null;
  const figure = useFigureStore((s) => (figureId ? s.figures[figureId] : undefined));
  const { onOpenFigure } = useEditorContext();

  const handleDoubleClick = useCallback(() => {
    if (!figureId) {
      return;
    }
    onOpenFigure?.(figureId);
  }, [figureId, onOpenFigure]);

  return (
    <NodeViewWrapper
      as="figure"
      data-type="figure"
      data-figure-id={figureId ?? undefined}
      className={`figure-block ${selected ? "is-selected" : ""}`}
      onDoubleClick={handleDoubleClick}
    >
      {figure ? (
        <div className="figure-block__preview">
          <FigureThumbnailPreview figure={figure} className="figure-block__thumb" />
          <figcaption className="figure-block__caption">
            <span className="figure-block__title">{figure.title}</span>
            <span className="figure-block__hint">双击在 Figure Studio 中编辑</span>
          </figcaption>
        </div>
      ) : (
        <div className="figure-block__placeholder">
          <span className="figure-block__label">Figure</span>
          <span className="figure-block__hint">
            {figureId ? "未找到关联的 Figure" : "缺少 figureId"}
          </span>
        </div>
      )}
    </NodeViewWrapper>
  );
}
