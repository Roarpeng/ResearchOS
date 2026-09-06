# ROADMAP 增补草案:Phase 6 — Scientific Manuscript(学术论文垂直域)

> 待并入 ResearchOS 仓库后合入 ROADMAP.md 与 docs/05-Development-Roadmap.md。对齐 ADR-0010/0011/0012
> (ResearchOS ADR 已编至 0009,论文域自 0010 起)。

## 目标

在 ResearchOS 闭环上实现**论文写作垂直域**:研究文件夹(日常资料/只言片语)→ 检索与证据 → 大纲与图规划
→ 逐节起草(仅锚定本人资料)→ 引用核验(幽灵引用=0)→ 期刊化 → PDF/投稿包 → 知识回流。

## 交付物

| 里程碑 | 内容 | 验收(映射 PaperHelp v3.0 M0–M3) |
|---|---|---|
| R0 单仓整合 | PaperHelp 历史并入 `apps/paperhelp/`;ADR 0008–0010 正式化;frontend/ TS workspace 骨架;Gateway 任务 API 连通冒烟 | frontend 能提交任务并收到流式事件;`apps/paperhelp` 树可构建 |
| R1 知识底座 | mcp-vault + knowledge ETL 接入;三通道检索;有据问答(frontend Vault 页) | 用户真实文件夹:文本解析成功率≥90%;中英混合 top-10 命中≥80%;问答引用 100% 可回溯 |
| R2 论文纵切 | 大纲(HITL)→ 逐节起草 → mcp-scholar 核验 → 期刊化 → PDF/投稿包 | 新论文 ≤2h 结构完整初稿;引用 100% 可解析;每段可溯源 |
| R3 图与数据闭环 | Figure Studio 移植完成;mcp-plot 沙箱 | CSV → 期刊风格图 ≤30min(含人工复核) |
| R4 习惯与小组 | 全局快捕、AI 对话归档、组会简报;小组形态评估 | 连续 4 周真实使用留存;快捕→入库 ≤5s |

## 依赖

- Phase 3 Knowledge Engine(full Compose 数据面)——R1 起依赖;
- Phase 2 Runtime + HITL——R2 起依赖;
- 前端移植依赖 ADR-0009 的 TS workspace 骨架。

## Non-Goals(域级)

- 不在 Python 侧重排版/编辑器;不承诺零幻觉;多人实时协同延后。
