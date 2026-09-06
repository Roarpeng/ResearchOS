# PaperHelp v3.0 — Research Memory + Manuscript Execution
# Architecture Design Document(Blueprint)

Version: 3.0(Blueprint)
Status: 待评审 Draft · 2026-09-06
Product: PaperHelp
定位:从 "Figure-first 写作台" 升级为 "资料记忆 + 论文执行" 的单研究者科研工作站

---

# 1. 背景与范式转换

PaperHelp v2.1(Alpha 已完成)解决的是:导入图片 → 自动排版 → 正文写作 → 导出 PDF 与投稿包。
它覆盖论文生产链条的**下游 30%**(排版、Figure 拼版、格式导出)。

v3.0 依据用户愿景把战线移到**上游 70%**:

> 日常将所有的科研资料、只言片语都放入一个文件夹;
> 系统基于这些资料与 AI 对话,完成论文、综述、数据制图等复杂产出。

范式转换:

| 维度 | v2.1(写作台) | v3.0(科研工作站) |
|---|---|---|
| 数据单元 | 单篇论文 `.paper` 容器 | 常驻 Vault 资料库(跨论文长期积累) |
| 输入 | 图片、docx | PDF/随手记/数据/照片/聊天记录/任何东西 |
| 结构 | 用户手工排版 | 先无结构捕获,系统事后反向建模 |
| 写作起点 | 空白编辑器 | "我的记忆"检索与大纲 Agent |
| 可信度 | — | 引用查表、生成必有源、幽灵引用=0 放行 |
| AI | 预留 `generate()` | 长任务编排 + Provenance 追溯 |

---

# 2. 用户画像与场景(已确认的决策)

- **学科**:植物 / 作物 / 农业科学(图件与期刊规范向该领域对齐)
- **使用者**:单研究者先行,架构预留小组/实验室形态(权限、共享库为 Phase 3+)
- **首个纵切场景**:单篇论文 — 从日常资料到大纲、正文、图表、投稿包的完整链路
- **AI 部署**:本地索引 + OpenAI 兼容云端推理(可替换 Provider);多语言 embedding 本地运行
- **捕获现状**:PDF 堆积、随手记散落、数据/图片为主、AI 对话想留存、习惯待养成
  → 产品第一责任是**把捕获做进日常(零摩擦)**,而不只是写作助手

目标期刊群(模板 CSS 对齐):Plant Physiology · Plant Cell · Journal of Integrative Plant
Biology · Crop Journal · Field Crops Research · Theoretical and Applied Genetics · 作物学报 ·
中国农业科学 等。

---

# 3. 产品原则(评审时的最高仲裁依据)

1. **零摩擦捕获**:拖进文件夹即入库;全局快捕;AI 对话可一键归档。整理是系统的事,不是用户的事。
2. **链接不复制**:Vault 与 `.paper` 是"引用关系",素材永远只有一份,不随论文拷贝。
3. **查表不生成**:引用元数据只来自 DOI/Crossref/OpenAlex/Semantic Scholar 查表,LLM 永不"编"引用。
4. **生成必有源**:任何长任务产出(段落/图表/结论)带证据链,可逐句回溯到源文件与页码。
5. **人在环裁决**:系统负责"读过、查过、起草过";用户负责"裁决、实验、署名"。分工透明、过程可查。
6. **代码优先于成品图**:数据→图 = 生成可复现脚本 → 沙箱执行 → 渲染入库,脚本随图归档。
7. **本地优先、Provider 可换**:索引/资料永不离开本机;推理走配置化的 OpenAI 兼容端点。
8. **AI 使用透明**:自动生成 AI 贡献声明草稿,适配期刊政策,不做黑箱代写。
9. **Working software first**:每里程碑端到端可验收,禁止过早 AI/过早云/架构洁癖(沿用 v2.1 §22)。

---

# 4. 机会依据(调研摘要)

痛点集中在"捕获之后"的记忆断裂与执行断层:

| 发现 | 量化/来源 |
|---|---|
| AI 综述的引用链系统性腐烂 | 50 篇 AI 辅助综述、5514 条引用中 **17% 无法解析到真实文献**(5.1% 纯幻觉;16.4% 标题真、元数据假;78.5% 解析错配)。"能写长文 ≠ 能投稿",可验证性才是产品护城河。 [The 17% Gap (Zenodo)](https://zenodo.org/records/18960183) |
| LLM 综述经不起同行评审 | 62 条 AI 生成引用中 84% 来自开放获取源,关键筛选步骤失败。[Springer 实验](https://rd.springer.com/article/10.1007/s00421-025-06100-w) |
| 有来源锚定也拦不住语义错误 | RAG 的"源锚定"无法消除语义治理失败,仍需要人在环。[Zenodo](https://zenodo.org/records/18109649) |
| 综合(synthesis)是文献工作最大瓶颈 | 工具评测把文献工作拆为 Discover/Screen/Extract/Read/Synthesize,无工具真正解决 Synthesize,综述多死于此步。[Ponder 2026 评测](https://ponder.ing/blog/best-ai-tools-for-literature-review) |
| 笔记不可复用 | "我知道它在库里,但每次都要重新找";研究生文献笔记不成体系。[科学网](https://news.sciencenet.cn/htmlnews/2021/10/466768.shtm) |
| 格式浪费可量化 | 57.3% 稿件因格式被退回重投,每年约 230 万小时耗于重排。[PLOS ONE](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0223976) |
| AI 尚未进入关键路径 | Nature 2025 调查仅约 4% 科学家认为 AI"必需"。 [澎湃](https://m.thepaper.cn/newsDetail_forward_24882066?commTag=true) |
| 图件制作成为公平性议题 | 资源少的研究组在科研图制作上更吃亏。[IPS News](https://ipsnews.net/business/2026/06/03/why-scientific-figures-are-becoming-an-equity-issue-in-research-publishing/) |
| 本地优先工作流兴起 | MCP 把模型接到自己的 Zotero/Obsidian,语义检索 + 控制权。[AI Without the Handover](https://www.thomasclaeys.be/evergreen/ai-without-the-handover-managing-research-with-model-context-protocol/);社区出现本地文件夹版 NotebookLM 与 Agent skills 论文流水线。[agentic-notebook](https://github.com/Harduex/agentic-notebook) · [dailypaper-skills](https://github.com/huangkiki/dailypaper-skills) |

竞争位:检索问答有 Consensus/SciSpace、读单篇有 NotebookLM/NotebookLM 类、提取有 Elicit、
写作润色有 Paperpal、白板综合有 Ponder、引用管理有 Zotero——**没有一款把"个人资料库记忆 +
长任务论文执行 + 期刊级 Figure/导出"放在一个本地产品里**。v3.0 打的是这条组合带。

---

# 5. 能力边界(三圈模型,产品红线)

**A 圈 · 可放心交给机器(成熟区)**
- 收件箱捕获解析:PDF/docx/md/txt/图片/CSV/聊天导出,哈希去重、增量索引
- 语义检索 + "问我的资料"有据问答(chunk 级引用)
- 资料反向结构化:只言片语聚类为 观点/假设/实验记录/待办
- 引用元数据核验(查表)与幽灵引用扫描
- 格式排版、Figure 拼版、投稿包(复用 v2.1 引擎)
- 数据→图:代码生成 → 沙箱执行 → 可复现产物

**B 圈 · 机器起草 + 人在环裁决(主战场,靠工程护栏)**
- 大纲 Agent:从资料提炼故事线,用户编辑裁决
- 逐节起草:只锚定本人资料,外补文献走查表;产出"证据链"可逐句接受/拒绝的 diff
- 综述/Related Work 初稿:冲突证据显式并列,不替用户"和稀泥"
- 长任务编排:任务清单 + 每步产物可审 + 断点续跑
- 工程护栏 = Provenance 追溯 + 差异评审 + 引用核验 + 产物即活对象(草稿进 Tiptap、图进 Figure Studio)

**C 圈 · 近期禁止承诺(产品红线)**
- 替用户裁决:证据权重、novelty、方法选择
- 无人值守端到端生成可投稿论文(行业 17% 幽灵引用率的教训)
- 用黑箱"流畅"输出冒充可辩护写作
- 结论:AI 负责"读过/查过/起草过",用户负责"裁决过/实验过/署名过"——写入产品文案与提示词系统。

---

# 6. 领域素材模型(作物/农学)

Vault 中出现的素材类型(解析器清单):

| kind | 例 | 入库动作 |
|---|---|---|
| pdf | 英文期刊论文/学位论文 | 全文文本+页码分块(扫描版→OCR,Phase M3) |
| docx/doc | Word 草稿、试验方案 | 文本分块,图片提取为 asset 引用 |
| md/txt | 随手记、会议纪要 | 原文 + 元数据 |
| image | 田间照片/显微图/无人机影像 | 缩略图+EXIF,不做 OCR(手写/图表 OCR 后续) |
| csv/xlsx | 表型、产量、生理、气象数据 | 结构化行块 + 列摘要(首期不分析) |
| chat | 与 AI 对话导出(DSH/各家) | 会话级分块,来源=chat |
| webpage | 网页笔记 | M3 |
| bib | .bib/.ris/DOI 粘贴 | 直接进 citations 查表归一 |

论文实体(单篇工作区,跨文档):研究问题 → 假设 → 试验设计 → 数据 → 结果 → 图 → 论断。
这些实体的提取是 M1+ 的"反向建模"目标,Vault 只保证存储与召回。

---

# 7. 总体架构

```text
+--------------------------------------------------------------+
|  UI Layer (React · Tailwind · shadcn)                        |
|  Editor(Tiptap) | Figure Studio(Konva) | Vault 页 | Agent 页  |
+--------------------------------------------------------------+
|  Domain Layer                                                 |
|  Document Engine | Figure Engine | Citation Engine           |
|  Vault Engine(ingest/index/retrieve)                          |
|  AI Engine(provider · tasks · provenance)                     |
+--------------------------------------------------------------+
|  Persistence:  Vault(vault.db + .paperhelp/) + .paper 容器     |
|  Runtime:      Tauri shell ↔ Node research-service sidecar     |
|                (解析/embedding/向量检索/沙箱脚本执行)            |
+--------------------------------------------------------------+
```

Monorepo 增量(v2.1 基础上):

```text
packages/
    ingest/       # 文件解析:pdf/docx/md/txt/csv/xlsx/img/chat → chunk
    knowledge/    # Vault:索引(全文+向量)、检索、重排、问答 grounding
    citations/    # DOI 查表(Crossref/OpenAlex/Semantic Scholar)、.bib/RIS 归一
    ai/           # Provider(OpenAI 兼容)+ Task 编排 + Provenance 记录
    editor/       # 复用;CitationNode 转真
    figure/       # 复用;接收 plot 产物与原始图
    db/           # .paper 容器(documents/blocks/assets)保持
    export/       # 复用;期刊模板 CSS 扩展
    shared/       # stores + types 扩展(assetStore → sourceStore 引用)
apps/
    desktop/      # Tauri;新增 Vault 页/Agent 面板;services/researchService.ts
scripts/
    research-service/   # Node sidecar 入口(解析/embedding/检索/沙箱)
```

**关键决策:Node sidecar 而非纯 Rust/纯 WebView**
理由:PDF 解析、embedding(ONNX/transformers)、向量检索、数据脚本沙箱在 Node 生态最成熟;
仓库已有 export-pdf.mjs 先例(Tauri 调 Node 脚本);Rust 只保留 v2.1 已用的文件对话框/图片元数据。
sidecar 与 UI 通过 JSON-RPC(stdin/stdout)或 127.0.0.1 随机端口通信;长期若需离线分发,
再评估 Rust 重写热路径。

### Vault 布局

```text
研究文件夹/                 # 用户可见:随意放置素材
└── .paperhelp/             # 系统目录(隐藏)
    ├── vault.db            # SQLite:全文 FTS5 + 向量(第一版) 
    ├── chunks/             # 解析文本缓存
    ├── thumbs/             # 图片缩略图
    ├── config.json         # provider 配置(baseURL/model/key 提示)
    └── provenance.jsonl    # AI 行为流水(供 AI 声明披露)
```

### 表设计草案(vault.db)

```sql
sources(id, path, sha256 UNIQUE, kind, mime, size, meta_json, first_seen, last_modified, status)
chunks(id, source_id FK, seq, text, page, section, token_count)
embeddings(chunk_id FK, model, dim, vector)      -- sqlite-vec 或外置 hnswlib
citations(id, doi UNIQUE, raw_json, normalized_json, verified_at)  -- 查表缓存,非 LLM 生成
ingest_jobs(id, root, started_at, finished_at, stats_json)
links(source_id, ref_id, kind)                   -- Vault ↔ .paper 引用(链接不复制)
```

`.paper` 内新增可选 `vault_refs.json`:记录引用过哪些 source/chunk,导出/归档时只带引用清单。

---

# 8. 端到端主流程:单篇论文纵切(M1 目标)

```text
[每日] 捕获:拖放/快捕/对话归档 → watch 入库 → 索引增量
  │
  ▼
[写论文] "帮我起草关于 X 的论文"
  ① 大纲 Agent      :资料聚类→故事线草案(含拟用图清单,映射到数据/原图)
                     → 用户在编辑器里改大纲、拖拽调整图序
  ② 图 Agent        :原图→Figure Studio 组图;CSV→plot 代码→沙箱渲染
                     → 每图挂一个论证节点(图-论断绑定)
  ③ 逐节起草 Agent  :IMRaD 逐节;只锚定 Vault;外补文献走 citations 查表
                     → 证据链视图:句 ← chunk ← 文件页
  ④ 核验 Agent      :交稿扫描——引用 100% DOI 可解析;矛盾声明显式列出
  ⑤ 期刊化          :模板 CSS(Plant Physiology 等)+ 图规范(dpi300/字号)
                     → PDF/投稿 ZIP(复用 v2.1)+ AI 使用声明草稿
```

产物流与验收均以 **"产物即活对象"** 为准:草稿落 Tiptap(带 CitationNode 真引用)、图落 Figure
Studio、证据链可在侧栏打开源文件页码、引用核验报告可导出附投稿包。

---

# 9. 里程碑(M0–M3)与验收

| 里程碑 | 内容 | 验收标准 | 周期估算 |
|---|---|---|---|
| **M0 资料库底座** | Vault watch 入库、全类型解析、多语言混合检索、"问我的资料"有据问答、真实文件夹验收 | 用户指定的真实混合文件夹:文本类解析成功率 ≥90%;中英混合查询 top-10 人工判定命中 ≥80%;问答引用 100% 可回溯到文件+页 | 2–3 周 |
| **M1 论文纵切** | 大纲 → 有源逐节草稿 → 引用核验 → PDF/投稿包(复用 v2.1 引擎);CitationNode 转真 | 新论文 ≤2h 得结构完整初稿;引用 100% 可解析;每段可溯源;产出含证据链与核验报告 | 3–4 周 |
| **M2 图与数据闭环** | 图规划 ↔ Figure Studio;CSV→代码→沙箱→期刊风格图 | 原始 CSV → 期刊风格图 ≤30min(含人工复核);脚本随图可复现 | 2–3 周 |
| **M3 习惯与长任务** | 全局快捕、AI 对话自动归档、组会简报、OCR(扫描 PDF)、小组形态评估 | 连续 4 周真实使用留存;快捕→入库 ≤5s;周报一键生成 | 3 周+ |

每阶段独立交付、独立验收;M1 未通前不做 M2 数据纵深;综述引擎置于 M1 验证之后。

---

# 10. 风险与合规

| 风险 | 应对 |
|---|---|
| 长任务不可靠(上下文溢出/半途而废) | 任务清单化、每步产物快照、断点续跑、差异评审,绝不单轮吐全稿 |
| LLM 引用幻觉(行业 17% 幽灵引用) | citations 只做查表;核验 Agent 在放行前扫描全部行内引用 |
| 有源锚定的语义错误 | 冲突并列而非调和;标注证据强度;用户裁决在链上 |
| 本地 embedding 质量不足(中↔英) | 默认多语言 bge-m3(q8 ONNX);M0 内做中文检索质量实测,不达标换模型 |
| 扫描版 PDF/手写 | M3 OCR;首期明确标注"未 OCR 源仅元数据可检索" |
| webview 与 sidecar 通信故障 | JSON-RPC 心跳、任务队列、UI 状态透明(索引进度/失败源列表) |
| 期刊 AI 政策 | 内嵌政策清单;AI 使用声明生成;不承诺"全自动代写" |
| 学术伦理/训练争议 | 人机分工可见(AI 行为流水 provenance.jsonl);过程可向导师展示 |
| .paper 与 Vault 双库混乱 | 链接不复制原则 + vault_refs.json;产品文案统一"素材一份,论文多篇引用" |
| 小组化需求提前 | 架构仅预留(路径级隔离),功能 Phase 3+ |

---

# 11. 决策记录(2026-09-06 讨论确认)

| 项 | 决策 |
|---|---|
| 学科 | 植物/作物/农业科学 |
| 首场景 | 单篇论文:大纲→草稿→投稿包 |
| 捕获现状 | PDF/随手记/数据图片/对话记录并存,习惯待养成 → 零摩擦捕获优先 |
| AI 部署 | 本地多语言 embedding + OpenAI 兼容云端推理 |
| 使用者 | 单研究者先行,小组预留 |
| 语料 | M0 验收使用用户指定的真实文件夹 |
| 本阶段动作 | 先落蓝图与开发计划文档,不改代码 |

---

# 12. 参考文档

- [PaperHelp_ADD_v2.1_Final.md](PaperHelp_ADD_v2.1_Final.md)(v2.1 架构)
- [docs/PROJECT_SUMMARY.md](docs/PROJECT_SUMMARY.md)(Alpha 交付明细)
- [M0 开发计划](docs/superpowers/plans/2026-09-06-paperhelp-v3.0-m0-vault-development.md)
- 调研依据见 §4 链接
