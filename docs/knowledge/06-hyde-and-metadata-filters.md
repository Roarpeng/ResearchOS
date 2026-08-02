# 06 — HyDE 与元数据过滤

## 目标

说明两类检索增强手段：

1. **HyDE（Hypothetical Document Embeddings）**：主要用于 **Review / 体验 / 痛点** 类查询，缩小「用户短问句」与「长评测文档」之间的语义鸿沟。  
2. **Metadata Filtering**：用 `model`、`source_file`、`timestamp` 等字段做硬约束，并支持 **近期 Reviews 窗口**。

二者均可在混合检索中叠加：先过滤候选空间，再对向量通道使用 HyDE 查询向量。

## HyDE

### 动机

用户查询往往是短句：「RS-200 噪音大吗？」「装配麻烦吗？」  
真实 Review chunk 是叙述性长文本。直接 embed 短查询，召回易偏规格页或标题页。

HyDE 流程：

```
User query
    │
    ▼
LLM 生成「假想评测段落」（不要求事实正确，只求分布像 Review）
    │
    ▼
Embed(hypothetical_doc)  —— 而非 Embed(query)
    │
    ▼
Qdrant Top-K（仍带 metadata filter）
    │
    ▼
与 Graph / BM25 结果融合（假想文本身不进入最终 Context 正文）
```

### 适用意图

| 适用 | 不适用 |
|------|--------|
| 体验、口碑、差评、痛点、易用性 | 精确规格数值、专利号、标准条款 |
| `section_type` 偏好 `review` | 纯 `parameter` / `table` 查询 |
| 查询短、口语化 | 查询已是完整说明书句子 |

`need_hyde` 由 Query Understanding 置位；也可在 MCP 参数强制开关。

### 假想文档生成约束

1. **风格**：模拟真实用户评测 / 论坛语气，包含可能的优缺点句式。  
2. **锚定**：提示中注入已知 `model` 过滤，避免串型号。  
3. **长度**：约 100–300 tokens，不宜长文。  
4. **事实**：明确告知模型「假设性，用于检索」；**禁止**把假想段落当作 citation 来源。  
5. **多假设（可选）**：生成 2–3 篇假想文分别检索，再对 chunk 投票 / RRF，提高召回，成本更高。

### 提示词骨架（逻辑）

```text
根据用户问题写一段假设的产品使用评测（非真实证据）。
产品型号：{models}
问题：{query}
要求：口语、含具体体验细节、可含痛点；不要编造精确实验室规格数字。
```

### 与 BM25 / Graph 的配合

- HyDE **只替换向量通道的查询向量**。  
- BM25 仍用原始 query（保留「噪音」「异响」等关键词）。  
- Graph 仍用实体链接到 Product → Review / PainPoint。  
- 融合后的 passages 必须来自真实索引，假想文仅作探针。

### 失败降级

| 情况 | 降级 |
|------|------|
| LLM 超时 / 失败 | 回退 `Embed(query)` |
| 假想文过短或空 | 回退原查询 |
| 召回全空 | 放宽 filter 一次或关闭 section 偏好再搜 |

### 观测

记录：`hyde_enabled`、`hyde_latency_ms`、`hyde_hit_gain`（相对非 HyDE 的新 chunk 数）。避免无增益时全局默认开启浪费 token。

---

## 元数据过滤（Metadata Filters）

### 核心字段

| 字段 | 含义 | 典型用法 |
|------|------|----------|
| `model` | 产品型号（数组或 keyword） | 竞品对比时限制两侧型号 |
| `source_file` | 原始文件名 / 逻辑名 | 「只信手册」「排除某份过期 PDF」 |
| `timestamp` | 文档或块时间（ISO-8601） | 时效、Review 窗口 |
| `workspace_id` | 租户隔离 | **强制**，安全边界 |
| `section_type` | 语义块类型 | 评测题偏 `review` |
| `doc_id` | 文档 ID | 单文档问答 |
| `language` | 语言 | 可选 |

过滤在 **Qdrant payload filter**、**OpenSearch bool filter**、**Neo4j WHERE** 三处语义对齐；不允许只在一处过滤导致串数。

### 过滤语义

1. **硬过滤（must）**：不满足则不可入选。`workspace_id` 永硬。  
2. **软偏好（should）**：boost `section_type`，但不删除其他类型（避免漏规格页里的相关句）。  
3. **否定过滤**：`source_file NOT IN ...` 用于排除已知噪声源。

### Qdrant 示意

```json
{
  "must": [
    {"key": "workspace_id", "match": {"value": "ws_..."}},
    {"key": "model", "match": {"any": ["RS-200"]}}
  ],
  "should": [
    {"key": "section_type", "match": {"value": "review"}}
  ]
}
```

### OpenSearch 示意

```json
{
  "bool": {
    "filter": [
      {"term": {"workspace_id": "ws_..."}},
      {"terms": {"model": ["RS-200"]}},
      {"range": {"timestamp": {"gte": "now-90d"}}}
    ]
  }
}
```

### Neo4j 示意

```cypher
MATCH (r:Review)-[:REFERENCES]->(c:Chunk)
WHERE r.timestamp >= datetime($since)
  AND ($models IS NULL OR any(m IN r.models WHERE m IN $models))
RETURN c
```

---

## 近期 Reviews 窗口（Recent Reviews Window）

### 定义

对 Review 类证据，默认仅采纳 `timestamp >= now - W` 的内容进入高优先级上下文。  
`W` 默认 **90 天**，可按工作区配置（30 / 90 / 180）。

### 行为细节

1. **窗口内**：正常参与融合排序。  
2. **窗口外**：默认丢弃；若全空，可自动扩窗一级（如 90→180）并在 diagnostics 标记 `review_window_expanded`。  
3. **非 Review 块**：规格 / 参数不受该窗口限制（除非用户显式要求「只要新手册」）。  
4. **缺失 timestamp**：Review 块缺时间则降权或移出窗口严格模式；入库时应尽量补齐（抓取时间 / 文档日期）。  

### 与 PainPoint 聚合

图谱聚合痛点时同样套用 Review 窗口，避免多年前投诉主导当前结论。Writer 若引用窗口外历史，必须显式标注时间。

---

## MCP / API 参数建议

```json
{
  "query": "装配是否繁琐？",
  "filters": {
    "models": ["RS-200"],
    "source_files": null,
    "timestamp_gte": null,
    "review_window_days": 90,
    "section_types": ["review"]
  },
  "hyde": {"enabled": true, "variants": 1}
}
```

## 验收场景

1. 同义口语评测问句：HyDE 开启比关闭命中更多真实 `review` chunk。  
2. `model=RS-200` 时不出现 RS-100 专属段落（硬过滤）。  
3. `review_window_days=30` 时 60 天前评论不进默认 Bundle。  
4. 假想评测文本永不出现在 citation 列表中。  
5. 三通道 filter 对同一查询排除集一致。
