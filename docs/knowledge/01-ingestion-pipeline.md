# 01 — 入库流水线（Ingestion Pipeline）

## 目标

将原始文档稳定、可追踪地转化为三通道索引（Neo4j / Qdrant / OpenSearch），并保留 MinIO 原始对象与 PostgreSQL 编排状态。

入库流水线是 Knowledge Layer 的写入面；检索面见 [05-hybrid-retrieval.md](./05-hybrid-retrieval.md)。

## 总体阶段

```
Acquire → Register → Store(Raw) → Parse → Chunk → Extract → Embed → Index → Verify
```

| 阶段 | 输入 | 输出 | 主要组件 |
|------|------|------|----------|
| Acquire | URL / 上传 / Git / 爬取结果 | 本地临时文件或流 | MCP search / browser / documents / github |
| Register | 文件元信息 | `doc_id`、状态=`registered` | PostgreSQL |
| Store(Raw) | 字节流 | MinIO `object_key` | MinIO |
| Parse | 原始对象 | 结构化 AST / Markdown / 表格 | Parser Router |
| Chunk | 结构化文档 | Semantic chunks | Chunker |
| Extract | Chunks | Entities + Relations | LLM / 规则抽取器 |
| Embed | Chunk texts | Vectors | Embedding Provider |
| Index | Chunks + Entities | Neo4j / Qdrant / OpenSearch 写入 | Indexers |
| Verify | 写入回执 | 状态=`ready` 或 `failed` | Validator |

## 文档生命周期状态

```
registered → storing → parsing → chunking → extracting → embedding → indexing → ready
                                                                              ↘ failed
                                                                              ↘ quarantined
```

- `ready`：三通道至少完成约定的最小集合（默认向量 + 全文必选；图抽取失败可降级为 `ready_degraded`）。
- `failed`：可重试；保留错误码与阶段。
- `quarantined`：解析或安全扫描失败，不进入检索。

## 1. Acquire（采集）

来源类型：

| 来源 | 典型工具 | 备注 |
|------|----------|------|
| 用户上传 | `documents.upload` | 直接进入 Store |
| Web 搜索结果 | `search()` | 仅元数据；正文需 crawl |
| 页面正文 | `browser` / `crawl` | HTML → 再 Parse |
| 仓库文件 | `github` | README、规格说明、issue |
| 已有对象 | MinIO 引用 | 重新解析 / 换 Embedding 模型 |

采集阶段必须记录：

- `acquired_at`
- `acquisition_channel`（upload / search / crawl / github / reindex）
- `original_url`（若有）
- `content_hash`（SHA-256）

相同 `content_hash` 在同一 workspace 内默认去重，避免重复索引。

## 2. Register（登记）

PostgreSQL `documents` 表（逻辑字段）：

| 字段 | 说明 |
|------|------|
| `doc_id` | 全局唯一 |
| `workspace_id` | 租户 / 项目隔离 |
| `title` | 可读标题 |
| `mime_type` / `extension` | 路由 Parser 的依据 |
| `source_file` | 原始文件名 |
| `object_key` | MinIO 路径 |
| `content_hash` | 去重键 |
| `status` | 生命周期 |
| `parser_name` / `parser_version` | 可复现 |
| `embed_model` / `embed_version` | 向量版本 |
| `language` | 可选 |
| `tags` / `models[]` | 业务过滤 |
| `created_at` / `updated_at` | 时间戳 |

## 3. Store(Raw) — MinIO

路径约定：

```
s3://researchos/{workspace_id}/raw/{doc_id}/original{ext}
s3://researchos/{workspace_id}/parsed/{doc_id}/v{n}/document.json
s3://researchos/{workspace_id}/parsed/{doc_id}/v{n}/document.md
```

规则：

1. 原始对象写入后默认不可变；重新解析生成新的 `parsed/.../v{n}`。
2. 删除文档采用软删除：检索侧下线，对象进入 `deleted/` 或保留 TTL。
3. 大文件分片上传；完成后校验 ETag / hash。

## 4. Parse（解析）

调用 Parser Router（详见 [02-document-parser-router.md](./02-document-parser-router.md)）：

| 扩展名 / MIME | Parser |
|---------------|--------|
| `.pdf` | Docling |
| `.pptx` / `.ppt` | MarkItDown |
| `.html` / `.htm` / 爬取 HTML | Unstructured |
| 其他（`.md` / `.docx` 等） | 扩展路由表；未匹配则 Unstructured 兜底 |

解析产物最小字段：

- 线性文本 / Markdown
- 标题层级树
- 页面或幻灯片编号
- 表格（结构化行列）
- 检测到的语言

## 5. Chunk（语义分块）

禁止主路径使用固定 500-token 切块。按 section 类型切分：

- `title` / `heading`
- `specification`（规格）
- `parameter`（参数）
- `table`（表格）
- `faq`
- `review`

详见 [03-semantic-chunking.md](./03-semantic-chunking.md)。

每个 chunk 必须携带：`doc_id`、`section_type`、`page`、`paragraph`、`source_file`、`timestamp`、可选 `model`。

## 6. Extract（实体与关系）

从 chunk（优先规格 / 参数 / 评测 / 新闻类）抽取：

**实体**：Product、Feature、Specification、PainPoint、Review、News、Company、Patent  

**关系**：HAS_FEATURE、COMPARES、REFERENCES、UPDATED_BY、PRODUCED_BY  

抽取策略：

1. 规则 / 词典：型号、单位、标准号高置信写入。
2. LLM 抽取：开放域特征、痛点、对比句。
3. 归一化：canonical name、单位换算、别名表。
4. 证据绑定：每条实体/关系至少 `REFERENCES` 到一个 `chunk_id`。

Schema 详见 [04-entity-and-schema.md](./04-entity-and-schema.md)。

## 7. Embed（向量化）

按 [08-embedding-strategy.md](./08-embedding-strategy.md) 选择模型：

优先级：**Voyage > OpenAI text-embedding-3-large > BGE-M3 > Nomic**  
本地 / 私有默认：**BGE-M3**

写入 Qdrant 时，同一 collection 内 `embed_model` 必须一致；换模型需新 collection 或全量 re-embed。

## 8. Index（三通道写入）

### Qdrant

- upsert point：`id=chunk_id`，vector + payload。
- payload 含过滤字段与 citation 基础字段。

### OpenSearch

- index document：`chunk_id` 为 `_id`。
- 字段：`text`、`section_type`、`model`、`source_file`、`timestamp`、以及规格 keyword 子字段。

### Neo4j

- MERGE 实体节点（幂等）。
- MERGE / CREATE 关系，属性含 `chunk_id`、`confidence`、`extracted_at`。
- Document / Chunk 节点可选物化，便于 `REFERENCES` 溯源。

写入顺序建议：先 OpenSearch / Qdrant（检索可用），再 Neo4j（图增强）；或事务外并行 + 最终 Verify。

## 9. Verify（校验）

最低检查：

1. MinIO 对象可读且 hash 匹配。
2. chunk 数量 > 0。
3. Qdrant 点数 = chunk 数（或可解释差异）。
4. OpenSearch docs = chunk 数。
5. 抽样 citation 字段完整（source、page/paragraph 或 url、time）。
6. 若启用图：至少尝试抽取；失败标记 `graph_status=degraded` 但不阻塞 `ready_degraded`。

## 失败与重试

| 失败阶段 | 策略 |
|----------|------|
| Store | 重试上传；超限 `failed` |
| Parse | 换兜底 parser 一次；再失败 `quarantined` |
| Chunk | 回退「标题层级粗分」；禁止静默固定 token 作为默认成功路径时不记警告 |
| Extract | 跳过图，进入 degraded |
| Embed | 换备用模型（需配置允许）或排队重试 |
| Index | 按通道独立重试；部分成功写补偿任务 |

所有重试写入 `ingestion_events` 审计日志。

## 增量与更新

- 同 URL / 同逻辑文档新版本：新 `doc_id` 或 `version++`，旧版 `superseded`。
- 图谱侧通过 `UPDATED_BY` 连接新旧 Product / Document 版本。
- 评测类文档可按 `timestamp` 进入「近期 Review 窗口」索引视图，无需物理删除历史。

## 与 MCP 的对应

| 流水线动作 | MCP 工具域 |
|------------|------------|
| 采集网页 / 搜索 | search、browser/crawl |
| 上传与对象读写 | documents |
| 解析 | parser |
| 图写入 / 查询 | kg write/query |
| 向量写入 / 检索 | vector upsert/search |
| 仓库资料 | github |

详见 [`../mcp/05-knowledge-tools.md`](../mcp/05-knowledge-tools.md)。

## 非目标

- 本流水线不负责最终报告排版（见 report export MCP）。
- 不在入库阶段做最终答案生成；LLM 仅用于抽取与可选分类。
- 不把原始 PDF 二进制直接塞进向量库。
