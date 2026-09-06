import { useCallback, useState } from "react";
import {
  buildFigureFromAssets,
  importImages,
  mergeFigureAssets,
} from "@paperhelp/figure";
import {
  executeFigureUpdate,
  InsertBlockCommand,
  useAssetStore,
  useCommandHistoryStore,
  useEditorStore,
  useFigureStore,
  type Asset,
  type EditorCommands,
} from "@paperhelp/shared";
import { Button, cn } from "@paperhelp/ui";
import { insertFigureIntoEditor } from "../utils/insertFigureIntoEditor";
import { FigurePropertiesPanel } from "./FigurePropertiesPanel";

interface AssetLibraryPanelProps {
  className?: string;
  editorCommands: EditorCommands | null;
}

function basename(path: string): string {
  const parts = path.split(/[/\\]/);
  return parts[parts.length - 1] ?? path;
}

function insertAssetAsFigure(
  editorCommands: EditorCommands,
  asset: Asset,
): void {
  const addFigure = useFigureStore.getState().addFigure;
  const recordCommand = useCommandHistoryStore.getState().record;
  const prevJSON = editorCommands.getJSON();
  const figure = buildFigureFromAssets([asset], basename(asset.path));

  addFigure(figure);
  editorCommands.focus();
  editorCommands.insertFigure(figure.id);

  const nextJSON = editorCommands.getJSON();
  recordCommand(
    new InsertBlockCommand(prevJSON, nextJSON, (json) => {
      editorCommands.setContent(json);
    }),
  );
}

export function AssetLibraryPanel({
  className,
  editorCommands,
}: AssetLibraryPanelProps) {
  const assets = useAssetStore((s) => Object.values(s.assets));
  const getThumbnail = useAssetStore((s) => s.getThumbnail);
  const selectedFigureId = useEditorStore((s) => s.selectedFigureId);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [previewAssetId, setPreviewAssetId] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);

  const selectedAsset = assets.find((asset) => asset.id === selectedAssetId);
  const previewAsset = assets.find((asset) => asset.id === previewAssetId);

  const handleImport = useCallback(async () => {
    setImporting(true);
    try {
      await importImages();
    } finally {
      setImporting(false);
    }
  }, []);

  const handleInsertFigure = useCallback(() => {
    if (!editorCommands) {
      return;
    }

    if (selectedAsset) {
      insertAssetAsFigure(editorCommands, selectedAsset);
      return;
    }

    insertFigureIntoEditor(editorCommands);
  }, [editorCommands, selectedAsset]);

  const handleAddToSelectedFigure = useCallback(() => {
    if (!selectedAsset || !selectedFigureId) {
      return;
    }

    const figure = useFigureStore.getState().figures[selectedFigureId];
    if (!figure) {
      return;
    }

    const merged = mergeFigureAssets(figure, [selectedAsset]);
    executeFigureUpdate(selectedFigureId, {
      assetIds: merged.assetIds,
      labels: merged.labels,
    });
  }, [selectedAsset, selectedFigureId]);

  return (
    <aside
      className={cn("asset-library", className)}
      aria-label="Image assets library"
    >
      <div className="asset-library__header">
        <span className="asset-library__title">图片资料</span>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={importing}
          onClick={() => void handleImport()}
        >
          {importing ? "导入中…" : "导入"}
        </Button>
      </div>

      <div className="asset-library__body">
        {assets.length === 0 ? (
          <p className="asset-library__empty">
            暂无图片。点击「导入」添加实验图、显微图等素材；也可在 Figure Studio 中导入。
          </p>
        ) : (
          <div className="asset-library__grid" role="list">
            {assets.map((asset) => {
              const thumbnail = getThumbnail(asset.hash);
              const isSelected = selectedAssetId === asset.id;

              return (
                <button
                  key={asset.id}
                  type="button"
                  role="listitem"
                  className={cn(
                    "asset-library__item",
                    isSelected && "asset-library__item--selected",
                  )}
                  onClick={() =>
                    setSelectedAssetId((current) =>
                      current === asset.id ? null : asset.id,
                    )
                  }
                  onDoubleClick={() => setPreviewAssetId(asset.id)}
                  title={basename(asset.path)}
                >
                  {thumbnail ? (
                    <img
                      src={thumbnail}
                      alt=""
                      className="asset-library__thumb"
                      draggable={false}
                    />
                  ) : (
                    <span className="asset-library__thumb asset-library__thumb--missing">
                      无预览
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}

        {selectedAsset ? (
          <div className="asset-library__actions">
            <p className="asset-library__selected-name">
              {basename(selectedAsset.path)}
            </p>
            <div className="asset-library__action-row">
              <Button
                type="button"
                size="sm"
                disabled={!editorCommands}
                onClick={handleInsertFigure}
              >
                插入 Figure
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => setPreviewAssetId(selectedAsset.id)}
              >
                预览
              </Button>
              {selectedFigureId ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={!editorCommands}
                  onClick={handleAddToSelectedFigure}
                >
                  加入当前 Figure
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>

      {selectedFigureId ? (
        <div className="asset-library__figure-panel">
          <FigurePropertiesPanel figureId={selectedFigureId} />
        </div>
      ) : null}

      {previewAsset ? (
        <div
          className="asset-library__preview-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label="Image preview"
          onClick={() => setPreviewAssetId(null)}
        >
          <div
            className="asset-library__preview-dialog"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="asset-library__preview-header">
              <span>{basename(previewAsset.path)}</span>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => setPreviewAssetId(null)}
              >
                关闭
              </Button>
            </div>
            {getThumbnail(previewAsset.hash) ? (
              <img
                src={getThumbnail(previewAsset.hash)}
                alt=""
                className="asset-library__preview-image"
              />
            ) : (
              <p className="asset-library__empty">无法加载预览</p>
            )}
          </div>
        </div>
      ) : null}
    </aside>
  );
}
