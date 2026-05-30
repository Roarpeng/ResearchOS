import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { FigureStudio } from "@paperhelp/figure";
import { useFigureStore } from "@paperhelp/shared";
import { Button } from "@paperhelp/ui";
import { FigurePropertiesPanel } from "../components/FigurePropertiesPanel";

export function FigureEditorPage() {
  const { id } = useParams<{ id: string }>();
  const selectFigure = useFigureStore((s) => s.selectFigure);
  const figure = useFigureStore((s) => (id ? s.figures[id] : undefined));

  useEffect(() => {
    if (id) {
      selectFigure(id);
    }
  }, [id, selectFigure]);

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
        <div className="figure-editor-page__title-group">
          <Button asChild variant="ghost" size="sm">
            <Link to="/">← 首页</Link>
          </Button>
          <h1 className="figure-editor-page__title">{figure.title}</h1>
        </div>
        <p className="figure-editor-page__hint">拖动画布元素；位置会吸附 {figure.layout.gridSize}px 网格</p>
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
