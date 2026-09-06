import type { RecoveryMarker } from "@paperhelp/db";
import { Button } from "@paperhelp/ui";

interface RecoveryDialogProps {
  marker: RecoveryMarker;
  onAccept: () => void;
  onDismiss: () => void;
}

export function RecoveryDialog({
  marker,
  onAccept,
  onDismiss,
}: RecoveryDialogProps) {
  const savedAt = new Date(marker.updatedAt).toLocaleString();

  return (
    <div className="recovery-dialog-backdrop" role="presentation">
      <div
        className="recovery-dialog"
        role="alertdialog"
        aria-labelledby="recovery-dialog-title"
        aria-describedby="recovery-dialog-description"
      >
        <h2 id="recovery-dialog-title" className="recovery-dialog__title">
          恢复未保存的文档？
        </h2>
        <p id="recovery-dialog-description" className="recovery-dialog__body">
          检测到上次未正常退出。是否恢复「{marker.title || "Untitled"}」？
          自动保存时间：{savedAt}
        </p>
        <div className="recovery-dialog__actions">
          <Button type="button" variant="outline" onClick={onDismiss}>
            放弃
          </Button>
          <Button type="button" onClick={onAccept}>
            恢复
          </Button>
        </div>
      </div>
    </div>
  );
}
