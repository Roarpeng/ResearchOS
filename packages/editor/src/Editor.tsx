import { useEditor, EditorContent } from "@tiptap/react";
import { BubbleMenu } from "@tiptap/react/menus";
import { useEditorStore } from "@paperhelp/shared";
import { Button } from "@paperhelp/ui";
import { getExtensions } from "./extensions";
import "./editor.css";

const INITIAL_CONTENT = `
<h1>Welcome to PaperHelp</h1>
<p>Start writing your paper here. Select text to format with the bubble menu.</p>
<p>You can use <strong>bold</strong>, <em>italic</em>, headings, and tables.</p>
`;

export function Editor() {
  const setDirty = useEditorStore((s) => s.setDirty);

  const editor = useEditor({
    extensions: getExtensions(),
    content: INITIAL_CONTENT,
    onUpdate: () => {
      setDirty(true);
    },
  });

  if (!editor) {
    return null;
  }

  return (
    <div className="paperhelp-editor">
      <BubbleMenu editor={editor} className="paperhelp-bubble-menu">
        <Button
          type="button"
          size="sm"
          variant={editor.isActive("bold") ? "secondary" : "ghost"}
          onClick={() => editor.chain().focus().toggleBold().run()}
        >
          Bold
        </Button>
        <Button
          type="button"
          size="sm"
          variant={editor.isActive("italic") ? "secondary" : "ghost"}
          onClick={() => editor.chain().focus().toggleItalic().run()}
        >
          Italic
        </Button>
        <Button
          type="button"
          size="sm"
          variant={
            editor.isActive("heading", { level: 1 }) ? "secondary" : "ghost"
          }
          onClick={() =>
            editor.chain().focus().toggleHeading({ level: 1 }).run()
          }
        >
          H1
        </Button>
        <Button
          type="button"
          size="sm"
          variant={
            editor.isActive("heading", { level: 2 }) ? "secondary" : "ghost"
          }
          onClick={() =>
            editor.chain().focus().toggleHeading({ level: 2 }).run()
          }
        >
          H2
        </Button>
        <Button
          type="button"
          size="sm"
          variant={editor.isActive("paragraph") ? "secondary" : "ghost"}
          onClick={() => editor.chain().focus().setParagraph().run()}
        >
          Paragraph
        </Button>
      </BubbleMenu>

      <EditorContent editor={editor} className="paperhelp-editor__content" />
    </div>
  );
}
