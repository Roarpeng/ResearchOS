# 源对话摘要：竞品分析工作流优化

本文固化 ChatGPT 设计对话 **「竞品分析工作流优化」**（[分享链接](https://chatgpt.com/share/6a6e9b45-842c-83ea-9cb0-a57f13126579)）中的关键结论，作为 ResearchOS 立项与文档补全的溯源说明。目标仓库：[github.com/Roarpeng/ResearchOS](https://github.com/Roarpeng/ResearchOS)。

## 1. 对话起点：原始 n8n RAG 方案

用户提出一套 **全开源、私有化** 的「自动检索 → 学习 → 分析 → 生成」竞品分析工作流：

| 模块 | 选型 | 作用 |
|------|------|------|
| 编排 | n8n | 核心工作流 + LangChain AI 节点 |
| 搜索 | SearXNG | 聚合搜索（JSON） |
| 对象存储 | MinIO | 原始 PDF/DOCX/PPT |
| 向量库 | Qdrant | 语义检索 + metadata 过滤 |
| 解析 | Docling / Unstructured | 复杂文档解析 |
| 本地模型 | Ollama（Qwen / Nomic） | 推理与 Embedding |
| 报告导出 | Gotenberg | HTML → PDF/DOCX |

流水线形态：

```text
Webhook → Qdrant 预查 →（不足则 SearXNG 抓取 → MinIO → Chunk → Embedding）
→ 多维 RAG 检索 → 单次大 Prompt 生成 Markdown → Gotenberg 转 PDF → SMTP
```

该方案适合快速私有化演示，但若目标是「持续积累、自动学习、自动生成多种行业分析」的平台，则偏 2024–2025 年 **线性 RAG Pipeline**，不足以支撑长期产品。

## 2. 推荐方向：Agent + Deep Research + MCP + Hybrid GraphRAG

对话结论将产品从「竞品分析 n8n 工作流」升级为 **Research Operating System**：

```text
原方案:  n8n + SearXNG + Chunk Embedding + 单 Prompt + Gotenberg
              │
              ▼
推荐:   Planner Agent
        → Research Agent
        → ETL Agent
        → Knowledge Graph + Vector (+ BM25)
        → Analysis Agents（规格/评价/定价/专利/竞品/风险/创新）
        → Reviewer Agent
        → Markdown Report → Typst / Pandoc
```

产品定位：

**ResearchOS = Deep Research + Knowledge OS + Engineering Copilot**

竞品分析是首个垂直场景，不是系统天花板。

## 3. 对话中的十二条改进要点（原文结构）

以下 12 点直接对应设计对话中的「第一部分…第十二部分」：

### 1）搜索层做成 Search Router（MCP Tool）

不要把 SearXNG 写成唯一入口。用 `search()` MCP 工具路由 SearXNG / Tavily / Brave 等，合并结果；后续也可接入带 Web Search 的云端模型，而不是在工作流里写死搜索。

### 2）不要只做向量：先抽实体再建库

`Document → Chunk → Embedding → Qdrant` 不够。应 `Docling → Entity Extraction → Knowledge Graph → Embedding → Qdrant`，把产品/特性/规格/痛点等抽成图，而不是只存文本块。

### 3）增加 Knowledge Graph，走 Hybrid RAG

查询走 **Graph Traversal + Vector Retrieval（+ Fulltext）**，例如 `Qdrant + Neo4j + BM25`，再一并交给 LLM。

### 4）文档解析用 Router，而不是单一引擎

保留 Docling；按格式路由：PDF → Docling，pptx → MarkItDown，html → Unstructured。

### 5）语义分块，而不是固定 Token 切片

按「标题 / 规格 / 参数 / 表格 / FAQ / Review」等语义单元切分，替代机械的 500-token chunk。

### 6）Embedding 策略分层

优先梯队：Voyage → OpenAI `text-embedding-3-large` → BGE-M3 → Nomic；本地默认推荐 **BGE-M3**。

### 7）拆多 Agent，禁止「一个大 Prompt」

Research / Parameter / Review / Innovation / Risk / Summary 等分工，最后 Merge Report，稳定性远高于单次生成。

### 8）强制 Citation 溯源

Chunk 保留 `source / page / paragraph / url / time / score`；报告可写「参数来自 PDF 第 16 页」。

### 9）先 Markdown，再用 Typst/Pandoc 导出

不要 HTML→PDF 直出。统一 Markdown 中间态，再 Typst→PDF 或 Pandoc→DOCX，排版与可 Diff 性更好。

### 10）增加 Planning Agent

先由 Planner 决定是否需要 Patent / GitHub / Reddit / YouTube / News / Paper，不同产品用不同搜索策略。

### 11）增加 Reviewer Agent

终稿前检查引用、遗漏参数、缺失竞品、矛盾陈述；不合格则退回 Research。

### 12）n8n 不做核心运行时

复杂逻辑放 Python / MCP；n8n 仅负责调度、定时、人工审批、通知与数据流转。

## 4. 平台级补充能力（对话收尾）

在十二条之上，对话进一步明确长期平台能力：

1. 多 Agent 协作（含 Citation 职责）
2. Hybrid RAG（BM25 + Qdrant + Neo4j）
3. MCP Tool 架构
4. LLM Agnostic（LiteLLM 路由）
5. 持续学习（RSS / 官网 / GitHub Release / 新闻增量）
6. 可扩展输出（PDF / DOCX / PPTX / Markdown / HTML / Notion / Confluence）

## 5. 与仓库文档的映射

| 改进点 | 文档落点 |
|--------|----------|
| 1 Search Router | [`docs/mcp/02-search-tools.md`](../mcp/02-search-tools.md)、[ADR-0007](../adr/0007-search-router-mcp.md) |
| 2–3 Graph + Hybrid RAG | [`docs/knowledge/`](../knowledge/README.md)、[ADR-0003](../adr/0003-hybrid-graphrag.md) |
| 4 Parser Router | [`docs/knowledge/02-document-parser-router.md`](../knowledge/02-document-parser-router.md) |
| 5 Semantic Chunk | [`docs/knowledge/03-semantic-chunking.md`](../knowledge/03-semantic-chunking.md) |
| 6 Embedding | [`docs/knowledge/08-embedding-strategy.md`](../knowledge/08-embedding-strategy.md) |
| 7 / 10 / 11 Agents | [`docs/agents/`](../agents/README.md) |
| 8 Citation | [`docs/knowledge/07-citation-provenance.md`](../knowledge/07-citation-provenance.md)、[`agents/08-Citation-Agent.md`](../agents/08-Citation-Agent.md) |
| 9 Report Pipeline | [ADR-0006](../adr/0006-report-pipeline-markdown-typst.md)、[`mcp/06-report-export-tools.md`](../mcp/06-report-export-tools.md) |
| 12 n8n 边界 | [ADR-0005](../adr/0005-n8n-orchestration-boundary.md) |
| 持续学习 | [`docs/workflows/03-continuous-learning.md`](../workflows/03-continuous-learning.md) |
| 竞品主流程 | [`docs/workflows/01-competitive-analysis.md`](../workflows/01-competitive-analysis.md) |

## 6. 文档补全意图

对话收尾的工程意图是：在 ResearchOS 仓库以 **文档驱动开发** 完成架构期交付——先补齐约数十份架构/ADR/专题文档，再进入基础设施与 Runtime 实现。本仓库本批文档即对应该意图的落地。

## 7. 一句话结论

**不要把竞品分析做成 n8n 上的线性 RAG 流水线；要建成可私有部署的 Agent 研究操作系统——以 MCP 为工具总线、以 Hybrid GraphRAG 为知识核心、以多 Agent + Reviewer + Citation 为研究闭环、以 n8n 为边缘调度与通知。**
