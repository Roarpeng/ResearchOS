import { Link, Outlet, useLocation } from "react-router-dom";
import { APP_NAME, useUiStore } from "@paperhelp/shared";
import { CommandPalette } from "../components/CommandPalette";
import { useThemeEffect } from "../hooks/useThemeEffect";

export function AppLayout() {
  useThemeEffect();

  const location = useLocation();
  const theme = useUiStore((s) => s.theme);
  const setTheme = useUiStore((s) => s.setTheme);
  const isEditorRoute = location.pathname.startsWith("/editor");
  const isFigureRoute = location.pathname.startsWith("/figure");
  const isFullBleedRoute = isEditorRoute || isFigureRoute;

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__brand">
          <Link to="/" className="app-header__logo">
            {APP_NAME}
          </Link>
          {isEditorRoute ? (
            <span className="app-header__route-label">编辑器</span>
          ) : null}
          {isFigureRoute ? (
            <span className="app-header__route-label">Figure Studio</span>
          ) : null}
        </div>

        <div className="app-header__controls">
          <span className="app-header__shortcut-hint">⌘K</span>
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

      <main className={isFullBleedRoute ? "app-main app-main--editor" : "app-main"}>
        <Outlet />
      </main>

      <CommandPalette />
    </div>
  );
}
