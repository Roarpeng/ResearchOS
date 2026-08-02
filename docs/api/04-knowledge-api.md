# 知识 API

知识 API 管理文档入库、混合检索、知识图谱查询与知识空间（Knowledge Space）。底层由 MinIO（原文）、PostgreSQL（元数据）、Qdrant（向量）、Neo4j（图谱）、可选 OpenSearch（全文）组成，对外统一由 Gateway 暴露。

## 目标

- 企业文档与研究产物可持久沉淀，支撑跨任务复用
- 检索为 **Hybrid GraphRAG**：向量 + 全文 + 图谱多跳，结果带引用溯源
- Agent 通过 MCP 调用同一能力；人类通过 REST 管理与调试

## 知识空间

知识空间是检索与权限的隔离单元，隶属于工作空间。

### 创建

`POST /api/v1/knowledge/spaces`

```json
{
  "workspace_id": "ws_01H...",
  "name": "协作机器人竞品库",
  "description": "厂商白皮书、标准、内部测评",
  "settings": {
    "embedding_model": "default",
    "chunk_size": 800,
    "chunk_overlap": 120,
    "enable_graph": true,
    "enable_opensearch": false
  }
}
```

响应：

```json
{
  "ok": true,
  "data": {
    "id": "kb_01H...",
    "name": "协作机器人竞品库",
    "status": "ready",
    "document_count": 0,
    "created_at": "..."
  }
}
```

### 列表 / 详情 / 更新 / 删除

| 方法 | 路径 |
|------|------|
| `GET` | `/api/v1/knowledge/spaces` |
| `GET` | `/api/v1/knowledge/spaces/{kb_id}` |
| `PATCH` | `/api/v1/knowledge/spaces/{kb_id}` |
| `DELETE` | `/api/v1/knowledge/spaces/{kb_id}` |

删除为软删 + 异步清理向量/图谱/对象；清理完成前 `status=deleting`。

## 文档入库

### 上传文件

`POST /api/v1/knowledge/spaces/{kb_id}/documents`

`multipart/form-data`：

| 字段 | 说明 |
|------|------|
| `file` | 文件本体（PDF、DOCX、PPTX、Markdown、TXT、HTML、图片 OCR 等，经 Docling） |
| `title` | 可选标题覆盖 |
| `tags` | JSON 数组字符串，如 `["cobot","safety"]` |
| `source_url` | 可选来源 URL |
| `metadata` | 可选 JSON 扩展字段 |

响应 `202`：

```json
{
  "ok": true,
  "data": {
    "id": "doc_01H...",
    "status": "queued",
    "filename": "iso-ts-15066.pdf",
    "bytes": 2048000,
    "ingest_job_id": "job_01H..."
  }
}
```

### 按 URL 入库

`POST /api/v1/knowledge/spaces/{kb_id}/documents/from-url`

```json
{
  "url": "https://example.com/whitepaper.pdf",
  "title": "厂商白皮书",
  "tags": ["vendor-a"]
}
```

由 MCP Browser/Fetch 工具或专用 worker 拉取；失败写入 `status=failed` 与错误原因。

### 入库流水线状态

```
queued → parsing → chunking → embedding → graph_extract → indexed
                                              ↘ failed
```

`GET /api/v1/knowledge/documents/{doc_id}` 返回状态、页数、chunk 数、实体数、错误信息。

### 文档列表与删除

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/knowledge/spaces/{kb_id}/documents` | 分页列表 |
| `GET` | `/api/v1/knowledge/documents/{doc_id}` | 详情 |
| `DELETE` | `/api/v1/knowledge/documents/{doc_id}` | 删除并清理索引 |
| `POST` | `/api/v1/knowledge/documents/{doc_id}/reindex` | 强制重建 |

### 原文下载

`GET /api/v1/knowledge/documents/{doc_id}/content`

- 鉴权后重定向到 MinIO 预签名 URL，或流式代理
- 记录审计：谁在何时下载了哪份文档

## 混合检索

`POST /api/v1/knowledge/search`

```json
{
  "workspace_id": "ws_01H...",
  "knowledge_space_ids": ["kb_01H..."],
  "query": "ISO/TS 15066 对协作机器人功率与力限制的要求",
  "mode": "hybrid",
  "top_k": 12,
  "filters": {
    "tags": ["safety"],
    "doc_ids": null,
    "date_from": null,
    "date_to": null
  },
  "options": {
    "include_graph": true,
    "rerank": true,
    "min_score": 0.2
  }
}
```

### `mode`

| 值 | 行为 |
|----|------|
| `vector` | 仅 Qdrant 语义检索 |
| `keyword` | 仅 OpenSearch/PostgreSQL FTS（无 OpenSearch 时降级） |
| `graph` | 仅 Neo4j 实体/路径检索 |
| `hybrid` | 融合以上通道并可选 rerank（默认） |

### 响应

```json
{
  "ok": true,
  "data": {
    "query": "...",
    "took_ms": 186,
    "hits": [
      {
        "id": "hit_1",
        "score": 0.87,
        "channel": "vector",
        "document_id": "doc_01H...",
        "chunk_id": "chk_...",
        "title": "ISO/TS 15066",
        "snippet": "...力与功率限制...",
        "citation": {
          "page": 14,
          "bbox": null,
          "source_url": null
        },
        "entities": ["ISO/TS 15066", "Power and Force Limiting"]
      }
    ],
    "graph_context": {
      "entities": [
        {"id": "ent_1", "name": "ISO/TS 15066", "type": "Standard"}
      ],
      "relations": [
        {"from": "ent_1", "type": "REFERENCES", "to": "ent_2"}
      ]
    }
  }
}
```

Agent 研究流程应优先消费 `hits[].citation`，写入任务证据库，保证终稿可追溯。

## 图谱查询

### 实体搜索

`GET /api/v1/knowledge/graph/entities?q=Universal+Robots&workspace_id=ws_...&limit=20`

### 邻居与路径

`POST /api/v1/knowledge/graph/expand`

```json
{
  "workspace_id": "ws_01H...",
  "entity_id": "ent_1",
  "depth": 2,
  "relation_types": ["HAS_FEATURE", "COMPARES", "REFERENCES"],
  "limit": 50
}
```

`POST /api/v1/knowledge/graph/path`

```json
{
  "workspace_id": "ws_01H...",
  "from_entity_id": "ent_1",
  "to_entity_id": "ent_9",
  "max_depth": 4
}
```

### 实体类型（与 GraphRAG 文档对齐）

Company、Product、Feature、Document、Patent、Standard、Review、Version 等；关系含 `HAS_FEATURE`、`COMPARES`、`REFERENCES`、`UPDATED_BY`、`PRODUCED_BY`。

工业扩展可增加 Robot、Controller、PLC、Skill、CADModel 等类型（Phase 5），不影响 v1 核心 API 形状。

## 研究产物回写

研究任务完成后，可将终稿或证据包写入知识库：

`POST /api/v1/knowledge/spaces/{kb_id}/documents/from-report`

```json
{
  "report_id": "rpt_01H...",
  "tags": ["generated", "competitor-analysis"],
  "include_citations_as_links": true
}
```

用于知识演化：研究报告成为后续检索语料，避免「一次性对话丢失」。

## 作业与进度

长耗时入库通过作业查询：

`GET /api/v1/knowledge/jobs/{job_id}`

```json
{
  "id": "job_01H...",
  "type": "ingest",
  "status": "embedding",
  "progress": 0.62,
  "document_id": "doc_01H...",
  "error": null
}
```

也可通过 WS `/api/v1/ws/knowledge/{job_id}` 订阅进度（可选，与研究 WS 事件风格一致）。

## 权限

| 操作 | 所需 scope |
|------|------------|
| 检索、读元数据、图谱只读 | `knowledge:read` |
| 上传、删除、重建、回写 | `knowledge:write` |
| 删除知识空间 | `knowledge:write` + 工作空间管理员策略 |

跨空间检索仅允许主体有读权限的 `knowledge_space_ids` 并集。

## 错误码（知识域）

| code | 含义 |
|------|------|
| `NOT_FOUND_SPACE` / `NOT_FOUND_DOCUMENT` | 资源不存在 |
| `VALIDATION_FILE_TYPE` | 不支持的文件类型 |
| `VALIDATION_FILE_TOO_LARGE` | 超过大小上限 |
| `CONFLICT_INGEST_IN_PROGRESS` | 重复提交冲突 |
| `UPSTREAM_QDRANT` / `UPSTREAM_NEO4J` / `UPSTREAM_MINIO` | 依赖失败 |
| `DEP_PARSER` | Docling/解析 worker 不可用 |

## 配置相关上限（建议默认）

| 项 | 默认 |
|----|------|
| 单文件大小 | 100 MB |
| 单次检索 `top_k` | 最大 50 |
| 图谱 `depth` | 最大 3（expand）/ 5（path） |
| 并发入库作业 / 空间 | 4 |

具体值由部署配置覆盖，见 [../deployment/02-configuration.md](../deployment/02-configuration.md)。

## 与 Agent / MCP 的关系

Gateway REST 是人类与 SDK 的入口；Runtime 内 Agent 通过 MCP Tools（`knowledge.search`、`knowledge.graph_expand`、`knowledge.ingest` 等）访问同一服务层，避免两套检索语义。MCP 工具的参数应可映射到本文 REST 字段。
