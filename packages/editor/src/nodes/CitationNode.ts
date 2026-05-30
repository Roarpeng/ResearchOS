import { Node, mergeAttributes } from "@tiptap/core";
import { ReactNodeViewRenderer } from "@tiptap/react";
import { CitationBlockView } from "../components/CitationBlockView";

export const CitationNode = Node.create({
  name: "citation",
  group: "block",
  atom: true,
  draggable: true,

  addAttributes() {
    return {
      id: {
        default: null,
      },
    };
  },

  parseHTML() {
    return [{ tag: 'div[data-type="citation"]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      "div",
      mergeAttributes(HTMLAttributes, { "data-type": "citation" }),
    ];
  },

  addNodeView() {
    return ReactNodeViewRenderer(CitationBlockView);
  },
});
