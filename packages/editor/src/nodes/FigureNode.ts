import { Node, mergeAttributes } from "@tiptap/core";
import { ReactNodeViewRenderer } from "@tiptap/react";
import { FigureBlockView } from "../components/FigureBlockView";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    figure: {
      insertFigure: (figureId: string) => ReturnType;
    };
  }
}

export const FigureNode = Node.create({
  name: "figure",
  group: "block",
  atom: true,
  draggable: true,

  addAttributes() {
    return {
      figureId: {
        default: null,
        parseHTML: (element) => element.getAttribute("data-figure-id"),
        renderHTML: (attributes) => {
          if (!attributes.figureId) {
            return {};
          }
          return { "data-figure-id": attributes.figureId };
        },
      },
    };
  },

  parseHTML() {
    return [{ tag: 'figure[data-type="figure"]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      "figure",
      mergeAttributes(HTMLAttributes, { "data-type": "figure" }),
    ];
  },

  addNodeView() {
    return ReactNodeViewRenderer(FigureBlockView);
  },

  addCommands() {
    return {
      insertFigure:
        (figureId: string) =>
        ({ commands }) =>
          commands.insertContent({
            type: this.name,
            attrs: { figureId },
          }),
    };
  },
});
