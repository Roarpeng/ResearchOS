import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./layouts/AppLayout";
import { EditorPage } from "./pages/EditorPage";
import { FigureEditorPage } from "./pages/FigureEditorPage";
import { HomePage } from "./pages/HomePage";
import "./App.css";

function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<HomePage />} />
        <Route path="editor" element={<EditorPage />} />
        <Route path="editor/:id" element={<EditorPage />} />
        <Route path="figure/:id" element={<FigureEditorPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
