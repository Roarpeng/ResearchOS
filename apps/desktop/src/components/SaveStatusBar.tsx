import { useEditorStore, type SaveStatus } from "@paperhelp/shared";

const SAVE_STATUS_LABELS: Record<SaveStatus, string> = {
  saved: "已保存",
  saving: "保存中…",
  unsaved: "未保存",
};

export function SaveStatusBar() {
  const saveStatus = useEditorStore((state) => state.saveStatus);
  const label = SAVE_STATUS_LABELS[saveStatus];

  return (
    <footer className="app-status-bar" role="status" aria-live="polite">
      <span
        className={`app-status-bar__indicator app-status-bar__indicator--${saveStatus}`}
      />
      <span className="app-status-bar__label">{label}</span>
    </footer>
  );
}
