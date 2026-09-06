import type { Editor } from "@tiptap/core";
import { EditorContent } from "@tiptap/react";

export interface EditorViewProps {
  editor: Editor;
}

export function InfiniteScrollView({ editor }: EditorViewProps) {
  return (
    <div className="paperhelp-scroll-view">
      <EditorContent editor={editor} className="paperhelp-editor__content" />
    </div>
  );
}
