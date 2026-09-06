# Phase 6 — Scientific Manuscript:执行状态(截至 2026-09)

> 分支 `feat/scientific-manuscript`;对应 ROADMAP Phase 6 提案(见 merge/ROADMAP-phase6-proposal.md)。

## 里程碑状态

| 里程碑 | 状态 | 已交付 | 验证 |
|---|---|---|---|
| R0 单仓整合 | ✅ | PaperHelp 历史 subtree 入 `apps/paperhelp/`;ADR-0010/0011/0012;`scientific/` 骨架;pyproject 注册 | 分支已推送;`npm run build` / pytest 绿 |
| R1 知识底座 | ✅ | `tools/vault`(MCP:scan/ingest/watch/capture/import_chat + SHA256 去重);Gateway `/api/v1/vault/*`;前端 `VaultPanel`;复用 knowledge 三通道检索 | 单测 + 本地端到端冒烟(parse→chunk→embed→hybrid search 带 citation)+ HTTP TestClient + 前端 build |
| R2 论文纵切 | 🟡 核心完成 | `tools/scholar`(resolve/lookup/verify 幽灵扫描);`scientific/manuscript`(stages/release_gate/provenance/draft/journalize/prompts) | 单测 17 项;Crossref 真实查表成功 |
| R3 图与数据闭环 | 🟡 核心完成 | `tools/plot`(数据→代码→沙箱渲染 PNG);前端 `FigureCanvas`(自动排版/标签/比例尺/PNG 导出) | plot 单测(真实渲染)+ 前端 build |
| R4 习惯与小组 | 🟡 部分 | 快捕 `append_note`、对话归档 `import_chat_transcript`、组会简报 `brief.py` | 单测 |

## 尚未完成(需 LLM/完整栈或更大工程)

1. **R2 LLM 胶水**:Writer/Reviewer 注册进 LangGraph runtime(接线方案见 `scientific/manuscript/README.md` §runtime 接线),需模型网关(LiteLLM)与 runtime 联调。
2. **R3 完整 Studio**:FigureCanvas 的标签/比例尺编辑、`plot.render` 产物接入画布、多图拖拽(PaperHelp 原 Figure Studio 全量交互)。
3. **R4 组会简报 LLM 化 / 小组形态**:当前 brief 为确定性版本;多人权限/共享库未做。
4. **期刊 PDF/DOCX 导出**:`journalize` 产出 HTML+manifest;PDF/DOCX 需接 `tools/report`(Typst/Pandoc)或前端 export 引擎。

## 验证证据速览

- 全量测试基线:474 passed(仓库原有 460+ 未被破坏)+ 本域新增 17 项全绿。
- 端到端冒烟:`scripts/smoke_vault.py`(摄取+去重+检索+溯源)。
- 前端:`npm run build`(tsc + vite)通过。
- 分支提交:已推送至 `origin/feat/scientific-manuscript`(网络正常时)。
