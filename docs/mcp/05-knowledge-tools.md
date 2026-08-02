# 05 — 知识工具（Knowledge Tools）

## 目标

通过 MCP 暴露知识层读写能力：**图谱写/查**、**向量 upsert/search**、以及面向 Agent 的 **混合检索门面**。底层引擎为 Neo4j、Qdrant、OpenSearch；原始文件仍在 MinIO。

设计背景见 [`../knowledge/GraphRAG.md`](../knowledge/GraphRAG.md) 与 [`../knowledge/05-hybrid-retrieval.md`](../knowledge/05-hybrid-retrieval.md)。

## 工具分组

| 组 | 工具 | 副作用 |
|----|------|--------|
| 门面检索 | `knowledge.retrieve` | 无 |
| 图谱 | `kg.query` / `kg.write` / `kg.upsert_entities` | 读 / 写 |
| 向量 | `vector.search` / `vector.upsert` / `vector.delete` | 读 / 写 |
| 全文（可选暴露） | `fulltext.search` | 无 |
| 入库辅助 | `knowledge.ingest_status` | 无 |

普通 Research / Writer 默认开放：`knowledge.retrieve`、`kg.query`、`vector.search`。  
写接口默认仅 Memory Agent 或带 `knowledge:write` 的自动化 worker。

---

## `knowledge.retrieve`（推荐门面）

一次性执行 Graph + Vector + BM25 融合，返回 Context Bundle。

**输入：**

```json
{
  "query": "RS-200 近期差评与额定扭矩",
  "filters": {
    "models": ["RS-200"],
    "source_files": null,
    "review_window_days": 90,
    "section_types": null
  },
  "hyde": {"enabled": "auto"},
  "top_k": 16,
  "include_subgraph": true
}
```

**输出：** 与知识层 Context Bundle 对齐（passages + citation + subgraph + diagnostics）。

行为要点：

- `hyde.enabled=auto` 时按意图启用（评测/痛点）。  
- 三通道并行；通道失败降级。  
- 所有 passage 含 provenance 字段。  

---

## 图谱工具

### `kg.query`

参数化图查询，**禁止**任意原始 Cypher 字符串暴露给不可信 Agent（管理员调试工具可另开 `kg.cypher_raw` 且默认关闭）。

**输入示例：**

```json
{
  "template": "product_specs",
  "params": {"product_key": "acme:rs-200", "limit": 50}
}
```

内置模板包括：`product_specs`、`product_compare`、`recent_painpoints`、`entity_evidence`、`produced_by`。

**输出：** nodes / edges / evidence_chunk_ids。

### `kg.write` / `kg.upsert_entities`

写入实体与关系（幂等 MERGE）。

**输入示例：**

```json
{
  "entities": [
    {
      "type": "Product",
      "canonical_key": "acme:rs-200",
      "properties": {"name": "RS-200"}
    }
  ],
  "relations": [
    {
      "type": "HAS_FEATURE",
      "from": {"type": "Product", "canonical_key": "acme:rs-200"},
      "to": {"type": "Specification", "canonical_key": "spec:rated_torque"},
      "properties": {"value": "12", "unit": "Nm", "chunk_id": "chk_..."}
    }
  ],
  "require_evidence": true
}
```

规则：

1. `require_evidence=true`（默认）时，关系必须带 `chunk_id` 或显式 `REFERENCES`。  
2. 关系类型白名单：`HAS_FEATURE`、`COMPARES`、`REFERENCES`、`UPDATED_BY`、`PRODUCED_BY`。  
3. 实体类型白名单：Product、Feature、Specification、PainPoint、Review、News、Company、Patent。  

---

## 向量工具

### `vector.search`

**输入：**

```json
{
  "query": "装配困难 螺丝 公差",
  "query_vector": null,
  "collection": null,
  "filters": {"models": ["RS-200"], "timestamp_gte": "2026-05-01T00:00:00Z"},
  "top_k": 20,
  "hyde": false
}
```

- 默认使用 workspace 主 embedding collection。  
- `hyde=true` 时内部生成假想评测再 embed。  
- 返回 chunk 文本 + payload + score + citation 字段。  

### `vector.upsert`

**输入：** chunks 数组（含 `chunk_id`、`text`、payload 元数据）。  

服务端负责 embed（按策略）或接受预计算向量（需 `vector:upsert_raw` 权限且维度校验）。  

### `vector.delete`

按 `chunk_id` / `doc_id` 软删或硬删；与 OpenSearch / 图证据清理作为补偿任务联动。

---

## `fulltext.search`（可选）

直接 BM25 通道，供调试或 Agent 在门面之外显式加强字面检索。生产提示词通常只需 `knowledge.retrieve`。

---

## `knowledge.ingest_status`

查询文档入库状态机：`registered…ready`，以及各通道成功标志（qdrant/opensearch/neo4j）。

---

## Documents 交叉

| 工具 | 作用 |
|------|------|
| `documents.upload` | 原始文件 → MinIO + 登记 |
| `documents.get` | 元数据 / 小文本 |
| `documents.link_url` | 登记 crawl 快照 |

知识工具假设 `doc_id` / `chunk_id` 已由入库产生；手工 upsert 须带齐 citation 元数据。

---

## GitHub 交叉

`github.get_file` / `github.search_code`（若启用）取回的文本应经 `documents` + `parser` 再进知识库，而不是直接 `vector.upsert` 无 provenance 的临时字符串——除非标记 `ephemeral=true` 且不进入长期索引。

---

## 权限矩阵（摘要）

| 工具 | research | memory | writer | planner |
|------|----------|--------|--------|---------|
| knowledge.retrieve | ✓ | ✓ | ✓ | ✓ |
| kg.query | ✓ | ✓ | ✓ | ✓ |
| vector.search | ✓ | ✓ | ✓ | 只读可选 |
| kg.write | 可选 | ✓ | ✗ | ✗ |
| vector.upsert | 可选 | ✓ | ✗ | ✗ |

细节见 [07-tool-security-and-permissions.md](./07-tool-security-and-permissions.md)。

## 错误与一致性

- 写图谱成功但向量失败 → 返回 `partial_ok` + 补偿任务 id。  
- 过滤字段非法 → `invalid_argument`。  
- collection 模型不匹配 → `embedding_mismatch`。  

## 验收

1. `knowledge.retrieve` 在无写权限 Agent 上可用。  
2. `kg.write` 缺 `chunk_id` 且 `require_evidence=true` 时拒绝。  
3. `vector.upsert` 后 `vector.search` 可命中，且 citation 字段完整。  
4. Review 窗口参数生效。  
5. HyDE 假想文不出现在 passages。
