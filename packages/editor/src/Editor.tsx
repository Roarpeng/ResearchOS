import { useEffect } from "react";
import { useEditor } from "@tiptap/react";
import { BubbleMenu } from "@tiptap/react/menus";
import { useEditorStore } from "@paperhelp/shared";
import { Button } from "@paperhelp/ui";
import { EditorProvider } from "./context/EditorContext";
import { getExtensions } from "./extensions";
import { InfiniteScrollView } from "./views/InfiniteScrollView";
import { A4PaginationView } from "./views/A4PaginationView";
import { extractHeadings } from "./utils/extractHeadings";
import { getSelectedFigureId } from "./utils/getSelectedFigureId";
import "./editor.css";

const INITIAL_CONTENT = `
<h1>Welcome to PaperHelp</h1>
<p>Start writing your paper here. Select text to format with the bubble menu.</p>
<p>You can use <strong>bold</strong>, <em>italic</em>, headings, and tables.</p>
`;

function syncDocumentState(
  getJSON: () => ReturnType<NonNullable<ReturnType<typeof useEditor>>["getJSON"]>,
  setDirty: (isDirty: boolean) => void,
  setOutline: ReturnType<typeof useEditorStore.getState>["setOutline"],
) {
  setDirty(true);
  setOutline(extractHeadings(getJSON()));
}

export interface EditorProps {
  onOpenFigure?: (figureId: string) => void;
}

export function Editor({ onOpenFigure }: EditorProps) {
  const setDirty = useEditorStore((s) => s.setDirty);
  const setOutline = useEditorStore((s) => s.setOutline);
  const setEditorCommands = useEditorStore((s) => s.setEditorCommands);
  const setSelectedFigureId = useEditorStore((s) => s.setSelectedFigureId);
  const viewMode = useEditorStore((s) => s.viewMode);

  const editor = useEditor({
    extensions: getExtensions(),
    content: INITIAL_CONTENT,
    onCreate: ({ editor: createdEditor }) => {
      setOutline(extractHeadings(createdEditor.getJSON()));
      setSelectedFigureId(getSelectedFigureId(createdEditor));
    },
    onUpdate: ({ editor: updatedEditor }) => {
      syncDocumentState(
        () => updatedEditor.getJSON(),
        setDirty,
        setOutline,
      );
    },
    onSelectionUpdate: ({ editor: updatedEditor }) => {
      setSelectedFigureId(getSelectedFigureId(updatedEditor));
    },
  });

  useEffect(() => {
    if (!editor) {
      return;
    }

    setEditorCommands({
      focus: () => {
        editor.chain().focus().run();
      },
      toggleHeading: (level) => {
        editor.chain().focus().toggleHeading({ level }).run();
      },
      insertFigure: (figureId) => {
        editor.chain().focus().insertFigure(figureId).run();
      },
    });

    return () => {
      setEditorCommands(null);
      setSelectedFigureId(null);
    };
  }, [editor, setEditorCommands, setSelectedFigureId]);

  if (!editor) {
    return null;
  }

  return (
    <EditorProvider onOpenFigure={onOpenFigure}>
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

        <div
          key={viewMode}
          className="paperhelp-editor__viewport"
          data-view-mode={viewMode}
        >
          {viewMode === "scroll" ? (
            <InfiniteScrollView editor={editor} />
          ) : (
            <A4PaginationView editor={editor} />
          )}
        </div>
      </div>
    </EditorProvider>
  );
}
