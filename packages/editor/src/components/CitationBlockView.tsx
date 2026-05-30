import { NodeViewWrapper } from "@tiptap/react";
import type { NodeViewProps } from "@tiptap/react";

export function CitationBlockView({ selected }: NodeViewProps) {
  return (
    <NodeViewWrapper
      as="div"
      data-type="citation"
      className={`citation-block ${selected ? "is-selected" : ""}`}
    >
      <div className="citation-block__placeholder">
        <span className="citation-block__label">Citation</span>
        <span className="citation-block__hint">Placeholder block</span>
      </div>
    </NodeViewWrapper>
  );
}
