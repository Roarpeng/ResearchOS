import { useState } from "react";
import { FigureCanvas, type FigureAsset } from "./figure/FigureCanvas";

/** Upload images → auto-layout Figure canvas → export PNG. */
export function FigurePanel({ onClose }: { onClose: () => void }) {
  const [assets, setAssets] = useState<FigureAsset[]>([]);

  function onFiles(files: FileList | null) {
    const list = Array.from(files ?? []);
    Promise.all(
      list.map(
        (f) =>
          new Promise<FigureAsset>((resolve, reject) => {
            const url = URL.createObjectURL(f);
            const img = new Image();
            img.onload = () =>
              resolve({ id: f.name, src: url, width: img.naturalWidth, height: img.naturalHeight });
            img.onerror = () => reject(new Error(`load ${f.name}`));
            img.src = url;
          }),
      ),
    )
      .then((loaded) => setAssets((prev) => [...prev, ...loaded]))
      .catch(() => {
        /* ignore individual load errors */
      });
  }

  function download(dataUrl: string) {
    const a = document.createElement("a");
    a.href = dataUrl;
    a.download = "figure.png";
    a.click();
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 960 }}>
        <div className="modal-head">
          <h2>图件 Figure</h2>
          <button type="button" className="ghost" onClick={onClose}>
            关闭
          </button>
        </div>
        <div className="modal-body" style={{ display: "grid", gap: 12 }}>
          <input
            type="file"
            accept="image/*"
            multiple
            onChange={(e) => onFiles(e.target.files)}
          />
          {assets.length > 0 ? (
            <FigureCanvas assets={assets} showScaleBar scaleBarLabel="20 µm" onExportPng={download} />
          ) : (
            <p>选择图片后自动排版(a/b/c 标签可点击改名,右下角比例尺,可导出 PNG)。</p>
          )}
        </div>
      </div>
    </div>
  );
}
