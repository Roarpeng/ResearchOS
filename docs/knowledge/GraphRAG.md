# GraphRAG Architecture

## 目标

ResearchOS 的 GraphRAG 不是「向量库 + 提示词」的薄封装，而是把**语义检索**与**关系推理**统一到同一条证据链上：

- 向量负责「像什么 / 语义相近」
- 全文（BM25）负责「精确词 / 型号 / 规格字面命中」
- 图谱负责「谁关联谁 / 多跳对比 / 来源演化」
- Citation 负责「答案每一句可回溯」

目标产出是 Agent 可直接消费的 **Context Bundle**：检索片段 + 图子图 + 引用元数据 + 融合分数。

## 为什么是 Hybrid

工业调研、竞品分析、专利解读等场景同时需要：

| 需求 | 单一向量不足 | Hybrid 如何补齐 |
|------|--------------|-----------------|
| 「A 型号与 B 型号差异」 | 文档可能不共现 | Neo4j `COMPARES` / 共特征路径 |
| 「额定扭矩 12Nm」 | Embedding 易漂 | BM25 / OpenSearch 精确命中 |
| 「近 90 天用户痛点」 | 无时间语义 | 元数据 `timestamp` + 近期 Review 窗口 |
| 「这句话出自哪一页」 | 常见 RAG 丢页码 | Citation provenance 强制保留 |

## 端到端流水线

```
外部源 / 上传文档
        │
        ▼
   MinIO（原始对象）
        │
        ▼
  Parser Router
  PDF → Docling
  PPTX → MarkItDown
  HTML → Unstructured
        │
        ▼
  Semantic Chunking
  （标题 / 规格 / 参数 / 表格 / FAQ / Review）
        │
        ├──────────────────┐
        ▼                  ▼
 Entity Extraction    Embedding
 Product / Feature /   Voyage > OpenAI >
 Spec / PainPoint /    BGE-M3 > Nomic
 Review / News /       （本地默认 BGE-M3）
 Company / Patent
        │                  │
        ▼                  ▼
     Neo4j              Qdrant
  实体 + 关系           向量 + payload
        │                  │
        └────────┬─────────┘
                 │
                 ▼
        OpenSearch BM25
         （全文索引）
                 │
                 ▼
         Hybrid Retrieval
    图召回 ∪ 向量召回 ∪ BM25
         RRF / 加权融合
                 │
                 ▼
     HyDE（可选，偏 Review）
     + Metadata Filters
                 │
                 ▼
      Citation Provenance
   source / page / paragraph
     url / time / score
                 │
                 ▼
         Agent Context Bundle
```

## 存储分工

### MinIO — 原始真相源

保存未解析二进制与解析中间产物（可选）：

- `raw/{workspace}/{doc_id}/original.*`
- `parsed/{workspace}/{doc_id}/structure.json`
- `artifacts/{workspace}/{doc_id}/tables/*.csv`

所有下游索引必须能通过 `source_file` / `object_key` 回到 MinIO 对象。

### Neo4j — 结构化关系

实体类型（核心）：

- `Product` / `Feature` / `Specification`
- `PainPoint` / `Review` / `News`
- `Company` / `Patent`

关系类型（核心）：

- `HAS_FEATURE`
- `COMPARES`
- `REFERENCES`
- `UPDATED_BY`
- `PRODUCED_BY`

图谱回答「实体如何连接」；不承担大段原文全文检索。

### Qdrant — 语义空间

每个 semantic chunk 一条向量点，payload 至少包含：

- `chunk_id`, `doc_id`, `section_type`
- `model`, `source_file`, `timestamp`
- `page`, `paragraph`, `url`
- `entity_ids[]`（可选反向链接）

### OpenSearch — BM25 全文

对 chunk 文本与关键规格字段建倒排索引，服务：

- 型号、SKU、标准号精确匹配
- 表格单元格字面检索
- 与向量结果互补的高召回通道

### PostgreSQL — 登记与编排元数据

文档状态机、解析版本、Embedding 模型版本、过滤字段字典、评测窗口配置。

## 检索融合概览

一次查询通常经历：

1. **Query Understanding**：抽取意图、实体提及、时间窗、型号过滤条件。
2. **并行召回**：
   - Graph：种子实体 → 1–2 跳邻居与关系路径
   - Vector：query（或 HyDE 伪文档）embedding → Top-K
   - BM25：query 关键词 → Top-K
3. **融合**：默认 Reciprocal Rank Fusion（RRF）；可对「规格精确问」提高 BM25 权重，对「体验/痛点」提高向量 / HyDE 权重。
4. **过滤**：`model` / `source_file` / `timestamp` / 近期 Review 窗口。
5. **重排与截断**：按融合分 + 多样性（同 doc 去重）生成 Context Bundle。
6. **挂载 Citation**：每条证据附 provenance 字段，供 Writer / UI 渲染。

详细算法见 [05-hybrid-retrieval.md](./05-hybrid-retrieval.md) 与 [06-hyde-and-metadata-filters.md](./06-hyde-and-metadata-filters.md)。

## Agent 消费契约（Context Bundle）

```json
{
  "query": "对比 A 与 B 的额定扭矩与近期差评",
  "filters": {
    "models": ["A", "B"],
    "review_window_days": 90
  },
  "passages": [
    {
      "chunk_id": "chk_...",
      "text": "...",
      "section_type": "specification",
      "score": 0.81,
      "channels": ["vector", "bm25"],
      "citation": {
        "source": "product-manual-a.pdf",
        "page": 12,
        "paragraph": 3,
        "url": null,
        "time": "2025-11-02T00:00:00Z",
        "score": 0.81
      }
    }
  ],
  "subgraph": {
    "nodes": ["Product:A", "Product:B", "Feature:rated_torque"],
    "edges": [
      {"type": "HAS_FEATURE", "from": "Product:A", "to": "Feature:rated_torque"},
      {"type": "COMPARES", "from": "Product:A", "to": "Product:B"}
    ]
  }
}
```

## 设计原则

1. **原始文件不可变**：MinIO 对象只追加新版本，不原地覆盖关键内容而不留版本号。
2. **分块跟结构走**：禁止默认固定 500-token 切块作为主策略。
3. **实体写入可幂等**：同一 `(type, canonical_key)` 合并，关系可带证据 `REFERENCES` 回链文档。
4. **检索通道可开关**：图 / 向量 / BM25 可按查询类型动态加权，但默认三者都启用。
5. **无 citation 不出报告正文断言**：Writer Agent 对无 provenance 的片段降权或不引用。

## 相关文档

- 入库：[01-ingestion-pipeline.md](./01-ingestion-pipeline.md)
- 解析路由：[02-document-parser-router.md](./02-document-parser-router.md)
- 语义分块：[03-semantic-chunking.md](./03-semantic-chunking.md)
- Schema：[04-entity-and-schema.md](./04-entity-and-schema.md)
- 混合检索：[05-hybrid-retrieval.md](./05-hybrid-retrieval.md)
- HyDE 与过滤：[06-hyde-and-metadata-filters.md](./06-hyde-and-metadata-filters.md)
- 引用溯源：[07-citation-provenance.md](./07-citation-provenance.md)
- Embedding：[08-embedding-strategy.md](./08-embedding-strategy.md)
- MCP 知识工具：[../mcp/05-knowledge-tools.md](../mcp/05-knowledge-tools.md)
