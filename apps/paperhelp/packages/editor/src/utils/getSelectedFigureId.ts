import type { Editor } from "@tiptap/core";

export function getSelectedFigureId(editor: Editor): string | null {
  const { selection } = editor.state;
  const { $from } = selection;

  for (let depth = $from.depth; depth >= 0; depth -= 1) {
    const node = $from.node(depth);
    if (node.type.name === "figure") {
      const figureId = node.attrs.figureId as string | null;
      return figureId ?? null;
    }
  }

  return null;
}
