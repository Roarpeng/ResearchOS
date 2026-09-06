import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useEditorStore, useUiStore } from "@paperhelp/shared";
import { cn } from "@paperhelp/ui";
import { insertFigureIntoEditor } from "../utils/insertFigureIntoEditor";

const COMMAND_PALETTE_ID = "command-palette";

interface CommandItem {
  id: string;
  label: string;
  keywords?: string;
  run: () => void;
}

export function CommandPalette() {
  const navigate = useNavigate();
  const isOpen = useUiStore((s) => s.isDialogOpen(COMMAND_PALETTE_ID));
  const closeDialog = useUiStore((s) => s.closeDialog);
  const toggleDialog = useUiStore((s) => s.toggleDialog);
  const viewMode = useEditorStore((s) => s.viewMode);
  const setViewMode = useEditorStore((s) => s.setViewMode);
  const editorCommands = useEditorStore((s) => s.editorCommands);

  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const close = useCallback(() => {
    closeDialog(COMMAND_PALETTE_ID);
    setQuery("");
    setActiveIndex(0);
  }, [closeDialog]);

  const commands = useMemo<CommandItem[]>(
    () => [
      {
        id: "view-scroll",
        label: "切换到 Scroll 视图",
        keywords: "scroll view mode",
        run: () => setViewMode("scroll"),
      },
      {
        id: "view-a4",
        label: "切换到 A4 视图",
        keywords: "a4 view mode pagination",
        run: () => setViewMode("a4"),
      },
      {
        id: "heading-h1",
        label: "插入 H1 标题",
        keywords: "heading h1 title",
        run: () => {
          if (editorCommands) {
            editorCommands.focus();
            editorCommands.toggleHeading(1);
          }
        },
      },
      {
        id: "heading-h2",
        label: "插入 H2 标题",
        keywords: "heading h2 subtitle",
        run: () => {
          if (editorCommands) {
            editorCommands.focus();
            editorCommands.toggleHeading(2);
          }
        },
      },
      {
        id: "heading-h3",
        label: "插入 H3 标题",
        keywords: "heading h3 section",
        run: () => {
          if (editorCommands) {
            editorCommands.focus();
            editorCommands.toggleHeading(3);
          }
        },
      },
      {
        id: "insert-figure",
        label: "插入 Figure",
        keywords: "figure insert image panel",
        run: () => {
          insertFigureIntoEditor(editorCommands);
        },
      },
      {
        id: "nav-home",
        label: "前往首页",
        keywords: "home navigate",
        run: () => navigate("/"),
      },
      {
        id: "nav-editor",
        label: "前往编辑器",
        keywords: "editor navigate write",
        run: () => navigate("/editor"),
      },
    ],
    [editorCommands, navigate, setViewMode],
  );

  const filteredCommands = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return commands;
    }

    return commands.filter((command) => {
      const haystack = `${command.label} ${command.keywords ?? ""}`.toLowerCase();
      return haystack.includes(normalized);
    });
  }, [commands, query]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    inputRef.current?.focus();
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        toggleDialog(COMMAND_PALETTE_ID);
        return;
      }

      if (!isOpen) {
        return;
      }

      if (event.key === "Escape") {
        event.preventDefault();
        close();
        return;
      }

      if (filteredCommands.length === 0) {
        return;
      }

      if (event.key === "ArrowDown") {
        event.preventDefault();
        setActiveIndex((index) => (index + 1) % filteredCommands.length);
        return;
      }

      if (event.key === "ArrowUp") {
        event.preventDefault();
        setActiveIndex(
          (index) =>
            (index - 1 + filteredCommands.length) % filteredCommands.length,
        );
        return;
      }

      if (event.key === "Enter") {
        event.preventDefault();
        filteredCommands[activeIndex]?.run();
        close();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeIndex, close, filteredCommands, isOpen, toggleDialog]);

  if (!isOpen) {
    return null;
  }

  const editorUnavailable = !editorCommands;

  return (
    <div className="command-palette-backdrop" onClick={close}>
      <div
        className="command-palette"
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onClick={(event) => event.stopPropagation()}
      >
        <input
          ref={inputRef}
          className="command-palette__input"
          value={query}
          onChange={(event) => setQuery(event.currentTarget.value)}
          placeholder="输入命令…"
          aria-label="Search commands"
        />

        <ul className="command-palette__list" role="listbox">
          {filteredCommands.length === 0 ? (
            <li className="command-palette__empty">未找到匹配的命令</li>
          ) : (
            filteredCommands.map((command, index) => (
              <li key={command.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={index === activeIndex}
                  className={cn(
                    "command-palette__item",
                    index === activeIndex && "command-palette__item--active",
                  )}
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => {
                    command.run();
                    close();
                  }}
                >
                  <span>{command.label}</span>
                  {command.id.startsWith("heading-") && editorUnavailable ? (
                    <span className="command-palette__hint">需打开编辑器</span>
                  ) : null}
                  {command.id === "insert-figure" && editorUnavailable ? (
                    <span className="command-palette__hint">需打开编辑器</span>
                  ) : null}
                  {command.id.startsWith("view-") ? (
                    <span className="command-palette__hint">
                      当前: {viewMode === "scroll" ? "Scroll" : "A4"}
                    </span>
                  ) : null}
                </button>
              </li>
            ))
          )}
        </ul>

        <div className="command-palette__footer">
          <span>↑↓ 选择</span>
          <span>Enter 执行</span>
          <span>Esc 关闭</span>
        </div>
      </div>
    </div>
  );
}
