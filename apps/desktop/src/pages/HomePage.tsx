import { useNavigate } from "react-router-dom";
import { useEditorStore } from "@paperhelp/shared";
import { Button } from "@paperhelp/ui";

export function HomePage() {
  const navigate = useNavigate();
  const reset = useEditorStore((s) => s.reset);

  const handleNewPaper = () => {
    reset();
    navigate("/editor");
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
        <Button type="button" size="lg" variant="outline" disabled>
          导入 Figure
        </Button>
        <Button type="button" size="lg" variant="outline" disabled>
          模板中心
        </Button>
      </div>
    </div>
  );
}
