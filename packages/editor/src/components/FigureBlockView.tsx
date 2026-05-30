import { NodeViewWrapper } from "@tiptap/react";
import type { NodeViewProps } from "@tiptap/react";

export function FigureBlockView({ selected }: NodeViewProps) {
  return (
    <NodeViewWrapper
      as="figure"
      data-type="figure"
      className={`figure-block ${selected ? "is-selected" : ""}`}
    >
      <div className="figure-block__placeholder">
        <span className="figure-block__label">Figure</span>
        <span className="figure-block__hint">Placeholder block</span>
      </div>
    </NodeViewWrapper>
  );
}
