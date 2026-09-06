import { EditorContent } from "@tiptap/react";
import "../styles/a4.css";
import type { EditorViewProps } from "./InfiniteScrollView";

export function A4PaginationView({ editor }: EditorViewProps) {
  return (
    <div className="paperhelp-a4-view">
      <div className="paperhelp-a4-page">
        <EditorContent editor={editor} className="paperhelp-editor__content" />
      </div>
    </div>
  );
}
