# 术语表 / Glossary

> 中英对照。实现与文档应使用此处的规范译名；新增术语请同步更新本文。

---

## A

### Agent（智能体）

在 ResearchOS 中，Agent 是具备**目标、工具使用权、局部策略与可观测输出**的执行单元。典型角色：Planner、Research、Reviewer、Writer、Memory。Agent 由 Runtime 调度，不直接暴露为无状态 HTTP Handler。

### Analysis Agent（分析智能体）

在证据与检索结果就绪后，执行对比、归因、风险评估、方案权衡等分析步骤的 Agent 族称。可与 Research Agent 分阶段，也可作为其子策略。

### ADR（Architecture Decision Record）

架构决策记录。记录 Context / Decision / Consequences / Alternatives。目录见 [`docs/adr/`](../adr/README.md)。

---

## B

### BM25

经典词法检索相关性算法。ResearchOS 用其（或经 OpenSearch 暴露的等价全文能力）补足向量检索对专有名词、型号、标准号的召回。

### Browser Tool（浏览器工具）

经 MCP 暴露的网页浏览/抓取能力，供 Research Agent 在搜索命中后阅读正文。需遵守robots/权限与速率限制策略。

---

## C

### Checkpoint（检查点）

LangGraph Runtime 将图执行状态持久化的快照。用于失败恢复、Human-in-the-loop 续跑、审计回放。通常落在 PostgreSQL（或 Runtime 配置的 checkpointer 后端）。

### Citation（引用）

报告中论断与**证据来源**的绑定。一条 Citation 至少包含：源 ID（URL/文档 ID）、定位（页码/段落/chunk id）、摘录或哈希、以及关联的 claim id。无 Citation 的关键论断应被 Reviewer 降权或标为待验证。

### Claim（论断）

研究过程中产生的可检验陈述。Claim 应关联 Evidence / Citation，并带置信度。

---

## D

### Deep Research（深度研究）

多步、工具增强、带规划与反思的研究范式，区别于单轮 RAG 问答。ResearchOS 将其产品化为可私有部署的 OS 能力。

### Docling

文档解析组件选项之一，偏向复杂版面/PDF 结构化抽取。与 MarkItDown、Unstructured 共同构成解析适配层。

---

## E

### ETL（Extract–Transform–Load）

研究与知识管线中的抽取–转换–装载：源文档/网页 → 清洗与语义分块 → Embedding / 实体关系抽取 → 写入 MinIO + PG + Qdrant + Neo4j + OpenSearch。

### Evidence（证据）

支持某 Claim 的原始材料片段（文本、表格、图注、元数据）。Evidence 进入 Memory / Knowledge 前应保留溯源字段。

### Embedding（嵌入）

文本（或多模态）到向量空间的映射，供 Qdrant 语义检索。通过 LiteLLM 或专用 embedding 端点调用，与 Chat 模型解耦。

---

## F

### Fulltext Search（全文检索）

基于词法/倒排索引的检索（BM25/OpenSearch）。Hybrid RAG 三通道之一。

---

## G

### Gateway（API 网关）

FastAPI 服务：认证、会话、REST/WebSocket 流式输出、向 Runtime 提交任务。不是 Agent 业务逻辑层。

### GraphRAG

结合知识图谱的检索增强：不仅召回相似文本，还利用实体关系路径扩展上下文。ResearchOS 的 Graph 侧以 Neo4j 为主。

### Hybrid RAG（混合检索增强）

**Graph + Vector + Fulltext** 三路召回与融合（加权/RRF/学习式路由）。对齐 ADR-0003。

---

## H

### Human-in-the-loop（人机回环）

在关键节点暂停图执行，等待人工批准、改写计划或补充约束，再从 Checkpoint 继续。

### HyDE（Hypothetical Document Embeddings）

先让 LLM 生成「假设性答案文档」，再以其 Embedding 做向量检索，改善短查询与语义鸿沟。可作为检索路由器的可选策略。

---

## K

### Knowledge Evolution（知识进化）

设计原则：研究与ETL产物持续更新组织知识层，使后续任务可复用实体、关系与证据。

### Knowledge Layer / Knowledge Engine

Neo4j + Qdrant + OpenSearch/BM25 + PostgreSQL 元数据 + MinIO 对象存储构成的持久智能层。

---

## L

### LangGraph

基于图/状态机的 Agent 编排框架。ResearchOS Agent Runtime 的选型，见 ADR-0001。

### LiteLLM

多模型统一网关，屏蔽 OpenAI / Anthropic / Google / 国产与本地推理差异。见 ADR-0004。

---

## M

### MarkItDown

微软系文档转 Markdown 工具，适合办公文档等到文本中间态的快速转换。解析适配层选项之一。

### MCP（Model Context Protocol）

向 LLM/Agent 暴露工具与资源的开放协议。ResearchOS 要求工具层 MCP-Native（ADR-0002）。

### MCP Server

实现一组 MCP Tools/Resources 的进程或服务（如 `search-router`、`kg-tools`、`report-render`）。

### Memory Agent

负责短期工作记忆与长期记忆写入策略的 Agent：何时入库、如何去重、如何关联任务与实体。

### MinIO

S3 兼容对象存储，存放原始文档、中间产物、报告制品等。

---

## N

### Neo4j

属性图数据库，存储实体与关系，支撑 GraphRAG 与关系型查询。

### n8n

开源自动化/iPaaS。在 ResearchOS 中**可选**，仅用于调度与通知，不承载核心研究状态机（ADR-0005）。

---

## O

### OpenSearch

分布式搜索引擎选项，提供全文检索、过滤与聚合；可承载 BM25 通道。

---

## P

### Pandoc

通用文档转换器；报告管线中可与 Typst 配合，输出 DOCX/PDF 等（ADR-0006）。

### Planner Agent（规划智能体）

将用户目标分解为可执行研究计划（任务图、工具预算、停止条件）。

### PostgreSQL

元数据、任务、用户、Checkpoint、Citation 索引等业务数据的主存储。

---

## Q

### Qdrant

向量数据库，存储 chunk / 实体描述等 Embedding，支撑语义召回。

---

## R

### RAG（Retrieval-Augmented Generation）

检索增强生成。ResearchOS 将其升级为 Hybrid RAG，并嵌入完整研究 OS，而非产品全部。

### Redis

缓存、队列辅助、速率限制、会话热数据等。

### Report Pipeline（报告管线）

`Evidence/Claims → Markdown 中间态 → Typst/Pandoc → PDF/DOCX`，见 ADR-0006。

### Research Agent（研究智能体）

执行检索、阅读、抽取证据、提出中间结论的核心 Agent。

### Reviewer Agent（评审智能体）

检查覆盖度、矛盾证据、引用完整性、幻觉风险，输出修改意见或放行。

### RRF（Reciprocal Rank Fusion）

多路检索结果融合的常用算法之一，按排名倒数加权合并。

### Runtime（运行时）

执行 Agent 图、管理 State/Checkpoint/流式事件的引擎层（LangGraph）。

---

## S

### Search Router（搜索路由器）

按查询类型、领域、权限把搜索请求路由到 Web / 学术 / 内部索引等后端的 MCP 工具（ADR-0007）。

### Semantic Chunk（语义分块）

按语义边界（段落/节/主题）切分文档，而非固定长度硬切。可保留父子块、重叠与结构元数据。

### Supervisor Agent（督导智能体）

顶层编排者：选择子 Agent、控制阶段迁移、处理失败与最终验收。自身不做深度研究。

---

## T

### Tool Budget（工具预算）

单次研究所允许的工具调用次数、浏览页数、费用或时延上限。由 Planner/Supervisor 管理。

### Typst

现代排版系统，用于将结构化 Markdown/数据渲染为高质量 PDF 报告（ADR-0006）。

---

## U

### Unstructured

文档解析库/服务选项，覆盖多种不规则文档格式。解析适配层之一。

---

## V

### Vector Search（向量检索）

基于 Embedding 相似度的语义召回，Hybrid RAG 三通道之一。

---

## W

### Writer Agent（写作智能体）

将通过评审的 Claims/结构大纲组织为 Markdown 报告，并触发报告渲染管线。

---

## 缩写速查

| 缩写 | 全称 |
|------|------|
| ADR | Architecture Decision Record |
| ETL | Extract, Transform, Load |
| GraphRAG | Graph-based RAG |
| HITL | Human-in-the-loop |
| HyDE | Hypothetical Document Embeddings |
| MCP | Model Context Protocol |
| RAG | Retrieval-Augmented Generation |
| RRF | Reciprocal Rank Fusion |
| SoT | Source of Truth（文档语境下常指 docs） |

---

## 相关文档

- [产品定义](./00-product-definition.md)
- [设计原则](./01-design-principles.md)
- [ADR 索引](../adr/README.md)
