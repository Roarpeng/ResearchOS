# frontend/src/manuscript — 论文域前端模块(占位)

PaperHelp UI 资产(Editor + Figure Studio)将并入此目录,作为 ResearchOS 现有 Vite 应用的模块。
详见 ADR-0011(文档根 `docs/adr/0011-frontend-import-paperhelp.md`)。

预期子目录:
- `editor/`   — Tiptap 双视图编辑器 + CitationNode(接 Gateway citation)
- `figure/`   — Konva Figure Studio(组图/标签/比例尺)
- `export/`   — 期刊化渲染 + PDF/投稿包(复用 PaperHelp export 引擎)
- `api.ts`    — 论文域 API 扩展(或并入现有 `src/api.ts`)

依赖将追加到 `frontend/package.json`(@tiptap/*、konva、react-konva、zustand 等)。
