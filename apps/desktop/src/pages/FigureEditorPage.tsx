import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  applyAutoLayout,
  applyLayout,
  FigureStudio,
  importImages,
  mergeFigureAssets,
  resolveFigureAssets,
  suggestAutoLayout,
} from "@paperhelp/figure";
import { useAssetStore, useFigureStore } from "@paperhelp/shared";
import { Button } from "@paperhelp/ui";
import { FigurePropertiesPanel } from "../components/FigurePropertiesPanel";

export function FigureEditorPage() {
  const { id } = useParams<{ id: string }>();
  const selectFigure = useFigureStore((s) => s.selectFigure);
  const figure = useFigureStore((s) => (id ? s.figures[id] : undefined));
  const updateFigure = useFigureStore((s) => s.updateFigure);
  const setLayoutPreview = useFigureStore((s) => s.setLayoutPreview);
  const clearLayoutPreview = useFigureStore((s) => s.clearLayoutPreview);
  const layoutPreview = useFigureStore((s) => (id ? s.layoutPreviews[id] ?? null : null));
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    if (id) {
      selectFigure(id);
    }
  }, [id, selectFigure]);

  const resolveAssets = useCallback(() => {
    if (!figure) return [];
    return resolveFigureAssets(
      figure,
      (assetId) => useAssetStore.getState().assets[assetId],
    );
  }, [figure]);

  const runAutoLayoutPreview = useCallback(() => {
    if (!id || !figure) return;
    const assets = resolveAssets();
    const preview = suggestAutoLayout(figure, assets);
    setLayoutPreview(id, preview);
  }, [figure, id, resolveAssets, setLayoutPreview]);

  const runApplyLayout = useCallback(() => {
    if (!id || !figure) return;
    const assets = resolveAssets();
    const patch = layoutPreview
      ? applyLayout(figure, layoutPreview)
      : applyAutoLayout(figure, assets);
    updateFigure(id, patch);
    clearLayoutPreview(id);
  }, [clearLayoutPreview, figure, id, layoutPreview, resolveAssets, updateFigure]);

  const handleImportImages = useCallback(async () => {
    if (!id || !figure) return;

    setImporting(true);
    try {
      const imported = await importImages();
      if (imported.length === 0) return;

      const merged = mergeFigureAssets(figure, imported);
      const assets = resolveFigureAssets(
        merged,
        (assetId) => useAssetStore.getState().assets[assetId],
      );
      const patch = applyAutoLayout(merged, assets);

      updateFigure(id, {
        assetIds: merged.assetIds,
        labels: merged.labels,
        ...patch,
      });
      clearLayoutPreview(id);
    } finally {
      setImporting(false);
    }
  }, [clearLayoutPreview, figure, id, updateFigure]);

  if (!id || !figure) {
    return (
      <div className="figure-editor-page figure-editor-page--empty">
        <p>未找到 Figure。</p>
        <Button asChild variant="outline" size="sm">
          <Link to="/">返回首页</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="figure-editor-page">
      <header className="figure-editor-page__toolbar">
        <div className="figure-editor-page__toolbar-row">
          <div className="figure-editor-page__title-group">
            <Button asChild variant="ghost" size="sm">
              <Link to="/">← 首页</Link>
            </Button>
            <h1 className="figure-editor-page__title">{figure.title}</h1>
          </div>
          <div className="figure-editor-page__actions">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={importing || figure.assetIds.length === 0}
              onClick={runAutoLayoutPreview}
            >
              自动排版
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={figure.assetIds.length === 0}
              onClick={runApplyLayout}
            >
              应用{layoutPreview ? "预览" : "排版"}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={importing}
              onClick={handleImportImages}
            >
              {importing ? "导入中…" : "导入图片"}
            </Button>
          </div>
        </div>
        <p className="figure-editor-page__hint">
          {layoutPreview
            ? "预览模式：半透明虚线框显示建议位置，点击「应用预览」写入画布"
            : `拖动画布元素；位置会吸附 ${figure.layout.gridSize}px 网格`}
        </p>
      </header>

      <div className="figure-editor-page__workspace">
        <section className="figure-editor-page__canvas" aria-label="Figure canvas">
          <FigureStudio figureId={id} className="figure-editor-page__studio" />
        </section>
        <FigurePropertiesPanel figureId={id} />
      </div>
    </div>
  );
}
