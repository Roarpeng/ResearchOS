import { useMemo } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { type SyncContext } from "@paperhelp/db";
import { APP_NAME, useEditorStore, useUiStore } from "@paperhelp/shared";
import { Button } from "@paperhelp/ui";
import { CommandPalette } from "../components/CommandPalette";
import { RecoveryDialog } from "../components/RecoveryDialog";
import { SaveStatusBar } from "../components/SaveStatusBar";
import { useAutosave } from "../hooks/useAutosave";
import { usePaperDocument } from "../hooks/usePaperDocument";
import { useRecoveryPrompt } from "../hooks/useRecovery";
import { useThemeEffect } from "../hooks/useThemeEffect";
import { readImageAssetForPaper } from "../services/paperIo";

export function AppLayout() {
  useThemeEffect();

  const location = useLocation();
  const theme = useUiStore((s) => s.theme);
  const setTheme = useUiStore((s) => s.setTheme);
  const isEditorRoute = location.pathname.startsWith("/editor");
  const isFigureRoute = location.pathname.startsWith("/figure");
  const isFullBleedRoute = isEditorRoute || isFigureRoute;
  const { busy: paperBusy, handleSave, handleOpen } = usePaperDocument();

  const syncContext = useMemo<SyncContext>(
    () => ({
      getEditorJSON: () => {
        const commands = useEditorStore.getState().editorCommands;
        if (!commands) {
          throw new Error("Editor is not ready");
        }
        return commands.getJSON();
      },
      setEditorJSON: (json) => {
        useEditorStore.getState().setDocumentContent(json);
        const commands = useEditorStore.getState().editorCommands;
        commands?.setContent(json);
      },
      readImageAsset: readImageAssetForPaper,
    }),
    [],
  );

  useAutosave(syncContext);
  const { marker, acceptRecovery, dismissRecovery } = useRecoveryPrompt(syncContext);

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
          {isEditorRoute ? (
            <div className="app-header__file-menu" role="group" aria-label="File">
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={paperBusy}
                onClick={() => void handleOpen()}
              >
                打开
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={paperBusy}
                onClick={() => void handleSave()}
              >
                保存
              </Button>
            </div>
          ) : null}
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

      {isEditorRoute ? <SaveStatusBar /> : null}

      <CommandPalette />

      {marker ? (
        <RecoveryDialog
          marker={marker}
          onAccept={() => void acceptRecovery()}
          onDismiss={() => void dismissRecovery()}
        />
      ) : null}
    </div>
  );
}
