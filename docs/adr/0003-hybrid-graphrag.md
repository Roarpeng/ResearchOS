# ADR-0003: 知识检索 — Hybrid GraphRAG

## Status

Accepted

## Context

深度研究与工程决策问题往往同时需要：

- **语义相似**召回（概念相近的段落）
- **词法精确**召回（型号、标准号、专利号、错误码）
- **关系推理**（竞品对比、供应链、版本演进、引用网络）

单一向量 RAG 在专有名词与多跳关系上系统性不足；纯图谱查询又缺乏语义模糊匹配。知识还必须经 ETL 持续进化，而非会话级临时上下文。

存储侧已倾向：

- Neo4j — 实体关系
- Qdrant — 向量
- OpenSearch / BM25 — 全文
- PostgreSQL — 元数据与引用索引
- MinIO — 原始对象

需要明确**检索架构决策**。

## Decision

采用 **Hybrid GraphRAG** 作为 Knowledge Layer 的检索范式：

```text
Query
  │
  ├─► Vector Search   (Qdrant)
  ├─► Fulltext/BM25   (OpenSearch or BM25 engine)
  └─► Graph Expansion (Neo4j entities & paths)
        │
        ▼
   Fusion (RRF / weighted) + optional Rerank
        │
        ▼
   Context Pack → Agents
```

具体决策点：

1. **三通道召回为默认**；允许路由器按 query 类型关闭某一通道。
2. **融合默认 RRF**，后续可引入学习式路由；重排模型可选。
3. **ETL 双写**：Semantic Chunk 入库向量与全文；实体/关系写入 Neo4j；对象原文进 MinIO。
4. **Citation 溯源**：所有进入 Context Pack 的片段必须可映射到 source_id + locator。
5. **可选检索增强**：HyDE、子问题分解、实体链接（Entity Linking）作为策略插件，而非硬编码唯一路径。
6. Graph 实体最小类型集：`Company`、`Product`、`Feature`、`Document`、`Patent`、`Standard`、`Person`、`Version` 等（可扩展）。

## Consequences

### 正面

- 覆盖语义、精确匹配与关系型问题。
- 与「Knowledge Evolution」原则一致，形成可复用组织记忆。
- 通道可独立扩缩容与替换（例如全文引擎可换）。

### 负面 / 成本

- 运维面扩大（多存储一致性、延迟尾部）。
- 需要数据质量治理：实体对齐、冲突合并、过期文档策略。
- 融合参数需要评测集调优，否则噪声上下文上升。

### 强制约束

- 禁止「只接一个向量库」作为生产默认架构宣传。
- 写入路径必须保留溯源元数据；无来源 chunk 不得进入正式知识库。

## Alternatives Considered

| 方案 | 结论 |
|------|------|
| 纯 Vector RAG | 不足以支撑竞品/专利/标准类关系问题 |
| 纯 Graph DB QA | 语义召回弱，对非结构化文档不友好 |
| 仅 Postgres全文 + LLM | 扩展性与语义能力不足 |
| 托管一体机知识库（闭源） | 违背私有部署与可审计原则，可作可选连接器而非核心 |
| LlamaIndex/Haystack 默认管线直接当 OS | 可用作库，但不替代我们显式的三通道架构决策 |
