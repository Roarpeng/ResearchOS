# ADR-0011: Frontend Integration & UI Strategy(PaperHelp UI 并入现有 frontend/)

Status: Draft(待并入 ResearchOS 后正式化)
Date: 2026-09-06(克隆后据真实仓库修订)
编号说明:承 ADR-0010(ResearchOS ADR 已编至 0009)。
关联:[ADR-0010](./0010-scientific-manuscript-domain.md)

## 背景(克隆后勘误)

ResearchOS 现已存在可运行的 `frontend/`(Phase 4 MVP):
- 技术栈:**npm + Vite 6 + React 19 + TypeScript ~5.7 + react-markdown**,单应用(非 pnpm workspace);
- 已有 `src/api.ts` 大型类型化 Gateway 客户端(基础 `/api/v1`,含 research/chat/knowledge/plc/settings/ws);
- 已有模块:`workbench/`(研究台)、`plc/`(PLC canvas)、`SettingsPanel`、`CitationRail`、`Timeline` 等。
PaperHelp 的 React 资产(Editor + Figure Studio)应**并入此现有应用**,而非另建 frontend。

## 决策

1. **PaperHelp UI 以模块形式并入现有 frontend/**,不替换、不另建:
   - `frontend/src/manuscript/` — 论文域模块:Editor(Tiptap 双视图)、Figure Studio(Konva)、
     CitationNode(接 Gateway citation 数据)、期刊化导出视图;
   - 新增 npm 依赖(@tiptap/*、konva/react-konva、zustand 等)进 `frontend/package.json`;
   - 复用 `src/api.ts` 的既有客户端;论文域端点不足处**扩展 api.ts**(而非新造独立客户端)。
2. **npm 单应用优先**(遵循现有 frontend 约定):先并入功能、跑通,后续确有需要再评估拆 workspace。
3. **Web 为主 + 可选 Tauri 壳**(用户已确认):Web 是主形态;Tauri 壳作为可选本地打包,不在首版承诺。
4. **迁移路径(非一次性大爆炸)**:
   - PaperHelp 历史已以子树并入 `apps/paperhelp/`(保留 blame/回滚,过渡目录);
   - 从中抽离 editor/figure/export/ui/shared 的源码,重构为 `frontend/src/manuscript/` 下的
     packages(或 `frontend/src/lib/{editor,figure,export}`),逐步替换原 `packages/*` 引用;
   - 全部迁移完成、验收通过后删除 `apps/paperhelp/` 过渡目录(历史仍在 git 中)。
5. **编辑器是活对象**:正文在浏览器 Tiptap 中编辑,CitationNode 变为真引用(数据源为 Gateway
   citation/mcp-scholar 缓存),FigureBlock 嵌入 Figure Studio 产物;Python 侧只消费 Markdown/结构化中间态。

## Consequences

- `.paper` 容器保留为「论文归档/导出格式」(可与 MinIO 对象互为副本);
- 导出 PDF/投稿包:复用 PaperHelp export 引擎(前端)与 ResearchOS `tools/report`(Typst/Pandoc)两条路径并存;
- 前端不持有模型密钥;所有模型调用经 Gateway;
- 既有 `src/api.ts` 是 api 客户端单一事实源,论文域扩展函数在其中追加并补 `Manuscript*` 类型。
