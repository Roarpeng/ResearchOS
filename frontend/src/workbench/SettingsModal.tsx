import SettingsPanel from "../SettingsPanel";

type SettingsModalProps = {
  onClose: () => void;
};

export function SettingsModal({ onClose }: SettingsModalProps) {
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal modal-settings"
        role="dialog"
        aria-label="设置"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-head">
          <h2>设置</h2>
          <button type="button" className="ghost" onClick={onClose}>
            关闭
          </button>
        </div>
        <SettingsPanel />
      </div>
    </div>
  );
}
