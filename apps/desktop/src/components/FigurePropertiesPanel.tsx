import {
  applyAutoLayout,
  applyLayout,
  detectCount,
  resolveFigureAssets,
  suggestAutoLayout,
} from "@paperhelp/figure";
import { useAssetStore, useFigureStore } from "@paperhelp/shared";
import { Button, cn } from "@paperhelp/ui";

interface FigurePropertiesPanelProps {
  figureId: string;
  className?: string;
}

export function FigurePropertiesPanel({ figureId, className }: FigurePropertiesPanelProps) {
  const figure = useFigureStore((s) => s.figures[figureId]);
  const selectedElementId = useFigureStore((s) => s.selectedElementId);
  const updateFigure = useFigureStore((s) => s.updateFigure);
  const layoutPreview = useFigureStore((s) => s.layoutPreviews[figureId] ?? null);
  const setLayoutPreview = useFigureStore((s) => s.setLayoutPreview);
  const clearLayoutPreview = useFigureStore((s) => s.clearLayoutPreview);

  if (!figure) {
    return (
      <aside className={cn("figure-properties", className)}>
        <p className="figure-properties__empty">未找到 Figure</p>
      </aside>
    );
  }

  const patch = (partial: Parameters<typeof updateFigure>[1]) =>
    updateFigure(figureId, partial);

  const resolveAssets = () =>
    resolveFigureAssets(figure, (assetId) => useAssetStore.getState().assets[assetId]);

  const handleAutoLayout = () => {
    const assets = resolveAssets();
    const preview = suggestAutoLayout(figure, assets);
    setLayoutPreview(figureId, preview);
  };

  const handleApplyLayout = () => {
    const assets = resolveAssets();
    const nextPatch = layoutPreview
      ? applyLayout(figure, layoutPreview)
      : applyAutoLayout(figure, assets);
    updateFigure(figureId, nextPatch);
    clearLayoutPreview(figureId);
  };

  const handleClearPreview = () => {
    clearLayoutPreview(figureId);
  };

  const preset = detectCount(figure.assetIds.length);

  const renderSelectionFields = () => {
    if (!selectedElementId) {
      return (
        <p className="figure-properties__hint">点击画布上的图片、标签或比例尺进行编辑。</p>
      );
    }

    if (selectedElementId === "scaleBar" && figure.scaleBar) {
      const bar = figure.scaleBar;
      return (
        <div className="figure-properties__section">
          <h3 className="figure-properties__section-title">比例尺</h3>
          <label className="figure-properties__field">
            <span>显示长度 (px)</span>
            <input
              type="number"
              min={20}
              value={bar.lengthPx}
              onChange={(e) =>
                patch({
                  scaleBar: { ...bar, lengthPx: Number(e.currentTarget.value) || 20 },
                })
              }
            />
          </label>
          <label className="figure-properties__field">
            <span>实际长度</span>
            <input
              type="number"
              min={0}
              step="any"
              value={bar.lengthValue}
              onChange={(e) =>
                patch({
                  scaleBar: {
                    ...bar,
                    lengthValue: Number(e.currentTarget.value) || 0,
                  },
                })
              }
            />
          </label>
          <label className="figure-properties__field">
            <span>单位</span>
            <input
              type="text"
              value={bar.unit}
              onChange={(e) =>
                patch({ scaleBar: { ...bar, unit: e.currentTarget.value } })
              }
            />
          </label>
        </div>
      );
    }

    if (selectedElementId.startsWith("label:")) {
      const labelId = selectedElementId.slice("label:".length);
      const label = figure.labels.find((entry) => entry.id === labelId);
      if (!label) return null;

      return (
        <div className="figure-properties__section">
          <h3 className="figure-properties__section-title">面板标签</h3>
          <label className="figure-properties__field">
            <span>文本</span>
            <input
              type="text"
              maxLength={8}
              value={label.text}
              onChange={(e) =>
                patch({
                  labels: figure.labels.map((entry) =>
                    entry.id === labelId
                      ? { ...entry, text: e.currentTarget.value }
                      : entry,
                  ),
                })
              }
            />
          </label>
        </div>
      );
    }

    if (selectedElementId.startsWith("image:")) {
      const assetId = selectedElementId.slice("image:".length);
      const item = figure.layout.items.find((entry) => entry.assetId === assetId);
      if (!item) return null;

      return (
        <div className="figure-properties__section">
          <h3 className="figure-properties__section-title">图片位置</h3>
          <label className="figure-properties__field">
            <span>X</span>
            <input
              type="number"
              value={item.x}
              onChange={(e) => {
                const x = Number(e.currentTarget.value) || 0;
                patch({
                  layout: {
                    ...figure.layout,
                    items: figure.layout.items.map((entry) =>
                      entry.assetId === assetId ? { ...entry, x } : entry,
                    ),
                  },
                });
              }}
            />
          </label>
          <label className="figure-properties__field">
            <span>Y</span>
            <input
              type="number"
              value={item.y}
              onChange={(e) => {
                const y = Number(e.currentTarget.value) || 0;
                patch({
                  layout: {
                    ...figure.layout,
                    items: figure.layout.items.map((entry) =>
                      entry.assetId === assetId ? { ...entry, y } : entry,
                    ),
                  },
                });
              }}
            />
          </label>
        </div>
      );
    }

    return null;
  };

  return (
    <aside className={cn("figure-properties", className)} aria-label="Figure properties">
      <div className="figure-properties__header">Figure 属性</div>

      <div className="figure-properties__body">
        <div className="figure-properties__section">
          <h3 className="figure-properties__section-title">Figure</h3>
          <label className="figure-properties__field">
            <span>标题</span>
            <input
              type="text"
              value={figure.title}
              onChange={(e) => patch({ title: e.currentTarget.value })}
            />
          </label>
          <label className="figure-properties__field">
            <span>画布背景</span>
            <input
              type="color"
              value={figure.style.backgroundColor}
              onChange={(e) =>
                patch({
                  style: { ...figure.style, backgroundColor: e.currentTarget.value },
                })
              }
            />
          </label>
        </div>

        <div className="figure-properties__section">
          <h3 className="figure-properties__section-title">自动排版</h3>
          <p className="figure-properties__hint">
            建议布局：{preset.label}
            {layoutPreview ? "（预览中）" : ""}
          </p>
          <div className="figure-properties__actions">
            <Button type="button" variant="outline" size="sm" onClick={handleAutoLayout}>
              自动排版
            </Button>
            <Button type="button" size="sm" onClick={handleApplyLayout}>
              应用{layoutPreview ? "预览" : ""}
            </Button>
            {layoutPreview ? (
              <Button type="button" variant="ghost" size="sm" onClick={handleClearPreview}>
                取消预览
              </Button>
            ) : null}
          </div>
        </div>

        {renderSelectionFields()}

        <div className="figure-properties__meta">
          <span>{figure.assetIds.length} 张图片</span>
          <span>网格 {figure.layout.gridSize}px</span>
        </div>
      </div>
    </aside>
  );
}
