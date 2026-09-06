# PaperHelp × ResearchOS 合并蓝图(Integration Blueprint)

Version: 1.0(Draft) · 2026-09-06
主题:将 PaperHelp(Figure-first 科研写作应用 + v3.0 资料记忆愿景)合并入 Roarpeng/ResearchOS
状态:待关键决策确认(见 §7)

---

# 1. 结论(先给答案)

**可以合并,而且这是当前最合理的走向。** 理由:

1. **愿景同构**:PaperHelp v3.0 要做的「资料记忆 + 长任务论文执行 + 可溯源产出」,正是 ResearchOS 的
   「Planner → Research → ETL → Knowledge → Analysis → Reviewer → Writer → Report」闭环在
   **学术论文垂直域**的实例;ResearchOS 产品定义中"学术/技术文献综述"本就是目标场景之一。
2. **能力互补,几乎零重叠**:

| PaperHelp 独有资产 | ResearchOS 独有资产 |
|---|---|
| React 编辑器(Tiptap 双视图/Outline) | Python Agent Runtime(LangGraph + Checkpoint + HITL) |
| Konva Figure Studio(组图/标签/比例尺) | FastAPI Gateway(REST/WS/SSE) |
| `.paper` 容器 + 导出(高保真 PDF/投稿 ZIP) | knowledge/(Docling 解析、chunking、Hybrid RAG) |
| docx 导入、FigureBlock、CitationNode 占位 | MCP 工具层(可审计)、LiteLLM 模型无关网关 |
| 本地离线桌面体验(Tauri) | 多 Agent(Supervisor/Planner/Research/Analysis/Reviewer/Writer/Memory) |
| 作物/农学语境(用户已确认的垂直领域) | workspace_id 权限基座、Docs-Driven(ADR)治理 |

3. **ResearchOS 目前没有 frontend/ 落地**:PaperHelp 的 React UI(编辑器 + Figure Studio)正好补上
   ResearchOS 缺失的交互层;反之 PaperHelp 一直没做的知识层/Agent 编排由 ResearchOS 直接继承。
4. 用户的「研究资料只言片语进文件夹」在 ResearchOS 里 = **Knowledge 层的日常摄取入口**;
   「据此写论文/综述/数据制图」= **学术垂直域的一组 Agent + MCP + 期刊化报告管线**。

---

# 2. 合并目标形态(推荐:ResearchOS 单仓 Polyglot Monorepo)

```text
ResearchOS/                          # 唯一上游仓库(保留 ResearchOS 全部历史)
├── frontend/                        # ★ 由 PaperHelp React 资产移植而来(Web UI)
│   ├── apps/                        #   页面:Home / Editor / Figure Studio / Vault / Tasks
│   ├── packages/
│   │   ├── editor/                  #   Tiptap 双视图编辑器(原 PaperHelp packages/editor)
│   │   ├── figure/                  #   Konva Figure Studio(原 figure)
│   │   ├── export/                  #   PDF/投稿包(原 export)
│   │   ├── db/                      #   .paper 容器兼容层(原 db)
│   │   ├── ui/ shared/              #   shadcn 与 stores(原 ui/shared)
│   │   └── api-client/              #   ★ 新增:Gateway/MCP 的 TS 客户端
│   └── desktop/                     #   ★ 可选:Tauri 壳,保本地桌面体验(离线模式走 lite)
├── gateway/                         # 既有 FastAPI Gateway(+ 论文域任务路由)
├── runtime/                         # 既有 LangGraph Runtime
├── agents/
│   ├── supervisor|planner|research|analysis|reviewer|writer|memory   # 既有
│   └── manuscript/                  # ★ 新增:论文域 Agent(见 §5)
├── tools/
│   ├── mcp-vault/                   # ★ 新增:研究文件夹 watch/ingest(文件夹即知识入口)
│   ├── mcp-scholar/                 # ★ 新增:Crossref/OpenAlex/Semantic Scholar 查表与检索
│   ├── mcp-plot/                    # ★ 新增:数据→代码→沙箱渲染→期刊图(可复现)
│   └── ...(既有 search-router 等)
├── knowledge/                       # 既有:ETL/parsers/chunking/embeddings/hybrid retrieval
│   └── schemas/scientific/          # ★ 新增:作物学实体 schema(genotype/treatment/phenotype...)
├── scientific/                      # ★ 新增:Python 领域包(论文垂直域核心,可选独立 pip 包)
│   ├── journal_styles/              #   期刊模板(Plant Physiology/Crop Journal...→ CSS/Typst)
│   ├── provenance/                  #   论断↔chunk↔来源 的溯源与核验(幽灵引用扫描)
│   └── manuscript/                  #   论文任务状态机复用层(在 runtime 之上)
├── deploy/                          # 既有 Compose + 新增 lite 本地模式说明
├── docs/                            # 既有 + 新增 ADR(见 §6)
└── (PaperHelp 历史以 apps/paperhelp/ 子树保留,便于 blame/回滚)
```

说明:
- ResearchOS 现为 Python 生态(uv),frontend 为 Node——采用**隔离 TS workspace**:`frontend/` 内自建
  pnpm workspace + Turbo,与根 Python 工程互不污染,仅在 CI 与脚本层联动(与 ResearchOS quick start
  中 `cd frontend && npm install` 的约定一致)。
- PaperHelp 现有 monorepo 目录(apps/desktop + packages/*)整体先入 `apps/paperhelp/`,再逐步将
  packages 上移/重映射到 `frontend/packages/*`,避免一次性大爆炸迁移;全部迁移完成后再移除过渡目录。

---

# 3. 分层映射(把 v3.0 蓝图落到 ResearchOS)

| PaperHelp v3.0 概念 | ResearchOS 承载 |
|---|---|
| Vault 文件夹(watch/入库) | `mcp-vault` + `knowledge/` ETL(替换原计划的 Node sidecar 自研解析) |
| 本地多语言 embedding | `knowledge/embeddings.py` + LiteLLM embed 路由(Qdrant/BM25 现成) |
| 有据问答(引用可回溯) | Research Agent + Context Pack + Citation 溯源(knowledge/retrieval 既有) |
| 幽灵引用扫描/DOI 查表 | `mcp-scholar`(查表不生成) + Reviewer 的引用检查阶段 |
| 大纲 Agent | Planner 阶段 + HITL 计划审批(与 Supervisor 人机回环一致) |
| 逐节起草 | Writer Agent 的 manuscript 子工作流(论断↔证据链) |
| 图/数据闭环 | Figure Studio(frontend)+ `mcp-plot`(沙箱) |
| 期刊化与导出 | Report MCP + Typst/CSS 期刊模板 + PaperHelp export 引擎 |
| 单篇论文归档 `.paper` | MinIO 对象 + 链接(或保留 .paper 作为导出格式) |

新增的领域 Agent 建议**不重造 Runtime**:在既有 Supervisor/Planner 之上注册论文域专用策略与停止条件;
Reviewer/Writer 复用,仅增加"引用必须可解析、矛盾显式并列、AI 使用声明"三条域规则。

---

# 4. 关键决策(已确认,2026-09-06)

D1 **单仓整合 ✓**:ResearchOS 为唯一上游,PaperHelp 以子树并入,保留历史。
D2 **数据面 ✓**:full Compose 数据面优先(PostgreSQL/Qdrant/Neo4j/MinIO/Redis),ResearchOS 标准部署;
    本地轻量模式(无 Docker)作为后续增强,不阻塞首版。
D3 **前端形态 ✓**:Web 为主(对齐 Gateway+WS),Tauri 壳作为可选"本地优先"打包方式保留。
D4 **Python 版论文域边界**:不把期刊写作排版搬进 Python;排版/编辑仍在前端(编辑器是活对象),
    Python 侧只负责检索、证据、起草中间态(Markdown)、核验与任务编排。
D5 **ADR 编号**:ResearchOS ADR 已编至 0009(0008/0009 为 PLC 域),论文域 ADR 自 0010 起。
D4 **Python 版论文域边界**:不把期刊写作排版搬进 Python;排版/编辑仍在前端(编辑器是活对象),
    Python 侧只负责检索、证据、起草中间态(Markdown)、核验与任务编排。

---

# 5. 论文域(Manuscript Domain)管线草案

```text
用户(编辑器/面板)──提交"起草一篇关于 X 的论文"
  Supervisor: 规划论文任务(大纲阶段,产出 outline 供 HITL 审批)
  Planner:     解析 X → 检索词 → mcp-vault/mcp-scholar 证据预算
  ETL/Knowledge: 命中资料入库(若新)→ 三通道召回 → Context Pack(带 citation)
  Analysis:    图/数据与论断的对应规划(哪些原图进 Figure Studio,哪些数据走 mcp-plot)
  Writer:      逐节起草(仅锚定 Vault + 已核验文献),Markdown 中间态
  Reviewer:    覆盖度 / 矛盾并列 / 引用 100% DOI 可解析 / AI 使用声明
  Writer:      期刊化渲染(模板)→ frontend 编辑器(活对象)或 Report 导出 PDF/投稿包
  知识回流:    最终论断 + 证据链回写 knowledge(下次任务受益)
```

规则(写进域提示词与 Reviewer 策略):查表不生成引用;生成必有源;冲突并列不调和;人在环裁决;
产出即活对象(草稿进 Tiptap、图进 Figure Studio);幽灵引用率=0 才放行。

---

# 6. 文档与治理(遵循 ResearchOS Docs-Driven)

合并前先在 ResearchOS 仓库新增/修订 ADR(可由本仓库 docs/ 起草后 PR):

- `ADR-0010: Scientific Manuscript Domain` — 论文垂直域范围、Persona(单研究者→小组)、Non-Goals、域规则
- `ADR-0011: Frontend Import from PaperHelp` — frontend/ 落地方式、TS workspace 隔离约定、编辑器/图资产归属
- `ADR-0012: Scholar / Vault / Plot MCP` — DOI 查表只读、文件夹摄取、数据→图沙箱与幽灵引用扫描策略
  (草案位于本仓库 docs/merge/adr-drafts/;ResearchOS ADR 已编至 0009,故自 0010 起)
- 本地轻量模式不再单独成 ADR,作为未来增强并入 ADR-0010 备注
- 同步更新:ROADMAP(新增 Phase 6 — Scientific Manuscript)、docs/core/00-product-definition(扩展目标场景)、README Status

# 7. 决策确认与执行入口(2026-09-06 已确认)

仓库形态=单仓整合;数据面=full Compose 优先;前端=Web 为主+可选 Tauri;执行=直接开工逐里程碑。
下一步(进程通道恢复后按 MIGRATION-MANIFEST 执行):
1) git clone ResearchOS → 单仓整合 PaperHelp 历史(apps/paperhelp 子树);
2) ADR 0010–0012 正式化 + ROADMAP Phase 6 合入 + frontend/ TS workspace 骨架(R0);
3) 逐里程碑 R1–R4(知识底座/论文纵切/图与数据闭环/习惯与小组),验收沿用 PaperHelp v3.0 M0–M3。

---

# 8. 参考

- ResearchOS README / ROADMAP / docs/00-Vision / 01-Architecture / core/00-product-definition(2026-09 抓取)
- PaperHelp_ADD_v2.1_Final.md、PaperHelp_ADD_v3.0_Blueprint.md(本仓库)
- PaperHelp v3.0 M0 开发计划(docs/superpowers/plans/2026-09-06-*)——合并后以 ResearchOS 组件重写该计划
