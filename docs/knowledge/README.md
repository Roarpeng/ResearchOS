# ResearchOS 知识层（Knowledge Layer）

ResearchOS 知识层是系统的持久智能核心，负责将外部文档、网页、评测与企业内部资料转化为可检索、可推理、可引用的结构化知识。

本目录文档描述 Hybrid GraphRAG 的完整设计：从原始文档入库，到语义分块、实体抽取、混合检索、HyDE、元数据过滤、引用溯源与 Embedding 策略。

## 设计目标

1. **知识可演化**：每次研究都会沉淀实体、关系与证据，而不是一次性上下文。
2. **检索可解释**：任何回答都可回溯到 source / page / paragraph / url / time / score。
3. **结构优先于暴力切块**：按文档语义结构（标题、规格、参数、表格、FAQ、Review）分块，而非固定 500 token。
4. **混合召回**：Neo4j 图推理 + Qdrant 向量语义 + BM25/OpenSearch 全文，三者融合。
5. **私有可部署**：原始文件落 MinIO；本地默认 Embedding 使用 BGE-M3。

## 文档索引

| 文档 | 内容 |
|------|------|
| [GraphRAG.md](./GraphRAG.md) | Hybrid GraphRAG 总览与端到端架构 |
| [01-ingestion-pipeline.md](./01-ingestion-pipeline.md) | 入库流水线：采集 → 存储 → 解析 → 分块 → 抽取 → 索引 |
| [02-document-parser-router.md](./02-document-parser-router.md) | Parser Router：按格式路由到 Docling / MarkItDown / Unstructured |
| [03-semantic-chunking.md](./03-semantic-chunking.md) | 语义分块策略与块元数据模型 |
| [04-entity-and-schema.md](./04-entity-and-schema.md) | 图谱实体、关系与 Neo4j Schema |
| [05-hybrid-retrieval.md](./05-hybrid-retrieval.md) | 图 + 向量 + BM25 融合检索 |
| [06-hyde-and-metadata-filters.md](./06-hyde-and-metadata-filters.md) | HyDE 评测检索与元数据过滤 |
| [07-citation-provenance.md](./07-citation-provenance.md) | 引用溯源与证据链 |
| [08-embedding-strategy.md](./08-embedding-strategy.md) | Embedding 选型、本地默认与切换策略 |

## 核心组件映射

| 能力 | 技术选型 | 职责 |
|------|----------|------|
| 对象存储 | MinIO | 原始 PDF / PPTX / HTML / 附件 |
| 文档解析 | Docling / MarkItDown / Unstructured | 结构化抽取文本与版面 |
| 向量库 | Qdrant | 语义检索、HyDE、过滤 |
| 图数据库 | Neo4j | 实体关系推理、多跳查询 |
| 全文检索 | OpenSearch（BM25） | 关键词、型号、规格精确命中 |
| 元数据 | PostgreSQL | 文档登记、任务状态、过滤索引 |
| 缓存 | Redis | 查询缓存、近期评测窗口辅助 |

## 与 MCP / Agent 的关系

- Agent 不直接操作存储后端，一律通过 MCP Knowledge / Parser / Documents 工具访问。
- Research Agent 负责采集与写入；Memory Agent 负责长期图谱维护；Writer Agent 消费带 citation 的检索结果。
- 详见 [`../mcp/README.md`](../mcp/README.md) 与 [`../mcp/05-knowledge-tools.md`](../mcp/05-knowledge-tools.md)。

## 阅读顺序建议

1. 先读 [GraphRAG.md](./GraphRAG.md) 建立全局图景。
2. 按 `01` → `08` 顺序理解入库到检索的数据流。
3. 实现 MCP 工具时对照 [`../mcp/05-knowledge-tools.md`](../mcp/05-knowledge-tools.md)。
