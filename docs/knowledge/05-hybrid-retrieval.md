# 05 — 混合检索（Hybrid Retrieval）

## 目标

将 **Neo4j 图召回**、**Qdrant 向量召回**、**OpenSearch BM25 全文召回** 融合为统一排序的 Context Bundle，供 Agent 推理与写作，并附着 citation。

## 通道职责

| 通道 | 引擎 | 擅长 | 不擅长 |
|------|------|------|--------|
| Graph | Neo4j | 多跳关系、对比、归属、版本 | 开放语义相似句 |
| Vector | Qdrant | 释义、同义、评测体验、跨语言（视模型） | 精确型号/数值字面 |
| BM25 | OpenSearch | 型号、规格字面、标准号、表格单元格 | 换说法的同义句 |

三者默认**并行召回**，再融合；禁止只做向量检索并称为 GraphRAG。

## 查询流水线

```
Query
  │
  ├─ Understand（意图 / 实体 / 过滤器）
  │
  ├─ Graph Retrieve ──────┐
  ├─ Vector Retrieve ─────┼─→ Fuse (RRF / 加权) → Filter → Diversify → Bundle
  └─ BM25 Retrieve ───────┘
```

### 1. Query Understanding

产出结构化查询意图：

```json
{
  "raw": "RS-200 和 RS-100 额定扭矩差多少？近三个月差评呢？",
  "intent": ["spec_compare", "review_sentiment"],
  "entities": ["RS-200", "RS-100"],
  "filters": {
    "models": ["RS-200", "RS-100"],
    "review_window_days": 90
  },
  "need_hyde": true,
  "channel_bias": {"bm25": 1.2, "vector": 1.1, "graph": 1.3}
}
```

启发式：

- 含型号 / 单位 / 精确数值 → 提高 BM25。  
- 含「对比 / 差异 / 竞品」→ 提高 Graph。  
- 含「体验 / 差评 / 痛点 / 好不好」→ 提高 Vector，并可能启用 HyDE（见 [06](./06-hyde-and-metadata-filters.md)）。  

### 2. Graph 召回

步骤：

1. 实体链接：query 提及 → Product / Company / Patent 节点。  
2. 扩展：1–2 跳 `HAS_FEATURE`、`COMPARES`、`PRODUCED_BY`、`UPDATED_BY`。  
3. 取证：沿 `REFERENCES` 收集 `chunk_id`。  
4. 将路径摘要为 `graph_snippets`（供 LLM）同时把 chunk 列入候选。

返回候选：`{chunk_id, graph_score, paths[]}`。

### 3. Vector 召回

1. 选择 embedding 模型（与 collection 一致）。  
2. 可选 HyDE：对 Review 类意图生成伪文档再 embed。  
3. Qdrant search：Top-K（如 30–50），带 payload filter（model / time 等）。  
4. 返回 `{chunk_id, vector_score, payload}`。

### 4. BM25 召回

1. 分析 query：保留型号、数字、单位 token。  
2. OpenSearch multi-match：`text^1`、`model^3`、`section_type` boost（parameter/specification/table）。  
3. 同等 metadata filter。  
4. 返回 `{chunk_id, bm25_score}`。

### 5. 融合（Fusion）

#### 默认：Reciprocal Rank Fusion（RRF）

\[
score(d) = \sum_{c \in channels} w_c \cdot \frac{1}{k + rank_c(d)}
\]

- \(k\) 默认 60。  
- \(w_c\) 来自意图偏置，默认全 1。  
- 未出现在某通道的文档不贡献该项。

#### 可选：加权归一化分

对各通道 score min-max 或 z-score 归一化后线性加权。适合通道分数标定稳定后使用。

#### 通道缺省

某通道失败时：降级为剩余通道融合，并在 Bundle `diagnostics.channels_failed` 记录，不整体失败。

### 6. 过滤与去重

1. 应用硬过滤：`model`、`source_file`、`timestamp`、权限 workspace。  
2. 近期 Review 窗口：对 `section_type=review` 或 Review 证据强制时间窗（可配置）。  
3. 多样性：同一 `doc_id` 最多 N 条；同一表格多行合并展示。  
4. 截断：按 token 预算选 Top-M passages + 子图节点上限。

### 7. Context Bundle 输出

见 [GraphRAG.md](./GraphRAG.md) 中的 JSON 契约。额外建议字段：

- `diagnostics`：各通道命中数量、融合参数、耗时  
- `subgraph`：精简节点边  
- `passages[].channels`：来自哪些通道  

## 意图 → 权重表示例

| 意图 | graph \(w\) | vector \(w\) | bm25 \(w\) | HyDE |
|------|-------------|--------------|------------|------|
| 规格精确查询 | 0.8 | 0.7 | 1.4 | 否 |
| 竞品对比 | 1.4 | 1.0 | 1.0 | 可选 |
| 用户痛点 / 评测 | 0.7 | 1.3 | 0.8 | **是** |
| 专利 / 标准号 | 1.1 | 0.6 | 1.5 | 否 |
| 开放调研综述 | 1.0 | 1.2 | 0.9 | 可选 |

## 延迟与并发

- 三通道并行；总超时（如 2–5s）内返回已完成通道。  
- Graph 复杂查询设跳数与边类型白名单，防止全图扫描。  
- Redis 可缓存「同 query hash + 同 filter」短 TTL 结果。

## 评估指标

| 指标 | 说明 |
|------|------|
| Recall@K（标注集） | 关键证据是否进入 Bundle |
| Citation 覆盖率 | 最终答案句子可追溯比例 |
| 通道贡献率 | 仅单通道命中却正确的比例 |
| 空结果率 | 应命中却三通道皆空 |
| p95 延迟 | 在线检索时延 |

离线应用应用「规格题 / 对比题 / 评测题」三套切片分别评估，避免只看平均。

## 反模式

1. 只搜 Qdrant，把 Neo4j 当摆设。  
2. 融合前不做 ID 对齐（必须统一 `chunk_id`）。  
3. 对数值题关闭 BM25。  
4. 把整图 dump 进 prompt。  
5. 丢掉 provenance 只留 text。

## 相关实现入口

- MCP：`kg.query`、`vector.search`、以及上层 `knowledge.search` / hybrid router。  
- 详见 [`../mcp/05-knowledge-tools.md`](../mcp/05-knowledge-tools.md)。
