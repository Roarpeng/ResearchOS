import { Editor } from "@paperhelp/editor";
import { useEditorStore, useUiStore } from "@paperhelp/shared";
import "./App.css";
import { useThemeEffect } from "./hooks/useThemeEffect";

function App() {
  useThemeEffect();

  const theme = useUiStore((s) => s.theme);
  const setTheme = useUiStore((s) => s.setTheme);
  const title = useEditorStore((s) => s.title);
  const setTitle = useEditorStore((s) => s.setTitle);
  const isDirty = useEditorStore((s) => s.isDirty);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__title">
          <input
            id="doc-title"
            className="doc-title-input"
            value={title}
            onChange={(e) => setTitle(e.currentTarget.value)}
            placeholder="Untitled"
            aria-label="Document title"
          />
          {isDirty ? <span className="dirty-indicator">Unsaved</span> : null}
        </div>

        <div className="app-header__controls">
          <label htmlFor="theme-select" className="sr-only">
            Theme
          </label>
          <select
            id="theme-select"
            className="theme-select"
            value={theme}
            onChange={(e) =>
              setTheme(e.currentTarget.value as "light" | "dark" | "system")
            }
          >
            <option value="light">Light</option>
            <option value="dark">Dark</option>
            <option value="system">System</option>
          </select>
        </div>
      </header>

      <main className="app-main">
        <Editor />
      </main>
    </div>
  );
}

export default App;
