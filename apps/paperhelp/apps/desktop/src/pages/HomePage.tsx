import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { importDocxDocument } from "@paperhelp/editor";
import { buildFigureFromAssets, importImages } from "@paperhelp/figure";
import { useAssetStore, useCommandHistoryStore, useEditorStore, useFigureStore } from "@paperhelp/shared";
import { Button } from "@paperhelp/ui";

export function HomePage() {
  const navigate = useNavigate();
  const reset = useEditorStore((s) => s.reset);
  const setTitle = useEditorStore((s) => s.setTitle);
  const setDocumentContent = useEditorStore((s) => s.setDocumentContent);
  const resetFigures = useFigureStore((s) => s.reset);
  const resetAssets = useAssetStore((s) => s.reset);
  const addFigure = useFigureStore((s) => s.addFigure);
  const assetCount = useAssetStore((s) => Object.keys(s.assets).length);
  const [importing, setImporting] = useState(false);
  const [importMessage, setImportMessage] = useState<string | null>(null);

  const handleNewPaper = () => {
    reset();
    useCommandHistoryStore.getState().clear();
    navigate("/editor");
  };

  const handleImportDocx = async () => {
    setImporting(true);
    setImportMessage(null);

    try {
      reset();
      resetFigures();
      resetAssets();
      useCommandHistoryStore.getState().clear();

      const result = await importDocxDocument();
      if (!result) {
        setImportMessage("未选择文档");
        return;
      }

      setTitle(result.title);
      setDocumentContent(result.content);
      navigate("/editor");
      setImportMessage(
        `已导入 ${result.paragraphCount} 段文字、${result.imageCount} 张图片（图片已加入资源库，可在 Figure Studio 中使用）`,
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "导入失败";
      setImportMessage(message);
    } finally {
      setImporting(false);
    }
  };

  const handleImportFigure = async () => {
    setImporting(true);
    setImportMessage(null);

    try {
      const assets = await importImages();
      const total = Object.keys(useAssetStore.getState().assets).length;
      if (assets.length === 0) {
        setImportMessage("未选择图片");
      } else {
        const figure = buildFigureFromAssets(assets);
        addFigure(figure);
        navigate(`/figure/${figure.id}`);
        setImportMessage(`已创建 Figure（${assets.length} 张图），资源库共 ${total} 个`);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "导入失败";
      setImportMessage(message);
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="home-page">
      <div className="home-page__hero">
        <h1 className="home-page__title">PaperHelp</h1>
        <p className="home-page__subtitle">Write and format academic papers.</p>
      </div>

      <div className="home-page__actions">
        <Button type="button" size="lg" onClick={handleNewPaper}>
          新建论文
        </Button>
        <Button
          type="button"
          size="lg"
          variant="outline"
          disabled={importing}
          onClick={handleImportDocx}
        >
          {importing ? "导入中…" : "导入文档"}
        </Button>
        <Button
          type="button"
          size="lg"
          variant="outline"
          disabled={importing}
          onClick={handleImportFigure}
        >
          {importing ? "导入中…" : "导入 Figure"}
        </Button>
        <Button type="button" size="lg" variant="outline" disabled>
          模板中心
        </Button>
      </div>

      {importMessage ? (
        <p className="home-page__import-status" role="status">
          {importMessage}
        </p>
      ) : null}

      {assetCount > 0 ? (
        <p className="home-page__asset-count">当前资源库：{assetCount} 个图片</p>
      ) : null}
    </div>
  );
}
