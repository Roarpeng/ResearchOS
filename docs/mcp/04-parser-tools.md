# 04 — 解析工具（Parser Tools）

## 目标

将知识层的 **Parser Router** 以 MCP 工具形式暴露，使 Agent 与入库 Worker 能用同一套接口完成类型检测、解析与（可选）语义分块调试。

底层路由规则见 [`../knowledge/02-document-parser-router.md`](../knowledge/02-document-parser-router.md)：

- PDF → **Docling**
- PPTX → **MarkItDown**
- HTML → **Unstructured**

## 工具列表

| 工具 | 副作用 | 说明 |
|------|--------|------|
| `parser.detect_type` | 无 | MIME / 扩展名 / 魔数检测 |
| `parser.list_parsers` | 无 | 可用解析器与版本 |
| `parser.parse` | 写（解析产物） | 执行解析，IR 落 MinIO |
| `parser.reparse` | 写 | 指定 parser 强制重解析，新版本号 |
| `parser.chunk` | 无或写 | 对 IR 做语义分块（调试或入库共用） |

## `parser.detect_type`

**输入：** `object_key` | `doc_id` | `filename` + 可选字节头  

**输出：**

```json
{
  "mime_type": "application/pdf",
  "extension": "pdf",
  "suggested_parser": "docling",
  "confidence": 0.98
}
```

## `parser.parse`

**输入：**

```json
{
  "doc_id": "doc_...",
  "object_key": null,
  "parser": "auto",
  "options": {
    "ocr": "auto",
    "language_hint": "zh"
  }
}
```

**行为：**

1. 定位 MinIO 原始对象（或先由 `documents` 登记）。  
2. `parser=auto` 时走路由表。  
3. 产出 Parse IR + Markdown，写入 `parsed/{doc_id}/v{n}/`。  
4. 更新 PostgreSQL：`parser_name`、`parser_version`、`status`。  

**输出：**

```json
{
  "ok": true,
  "doc_id": "doc_...",
  "parser_used": "docling",
  "ir_object_key": "ws/.../parsed/.../document.json",
  "markdown_object_key": "ws/.../parsed/.../document.md",
  "stats": {"pages": 24, "tables": 5, "warnings": 1},
  "warnings": ["low_ocr_confidence:page=7"]
}
```

不在响应中内联整本 IR；Agent 需要时可 `documents.get` 有限片段或直接进入 `parser.chunk` / ingestion。

## `parser.reparse`

与 `parse` 类似，但要求显式 `parser` 或 `force_version=true`，用于：

- 路由错误纠正  
- OCR 开关变更  
- parser 大版本升级后回填  

旧 `v{n}` 保留，便于对比。

## `parser.chunk`

对已存在 IR 执行语义分块（规则见 [`../knowledge/03-semantic-chunking.md`](../knowledge/03-semantic-chunking.md)）。

**输入：**

```json
{
  "doc_id": "doc_...",
  "persist": true,
  "section_types_allowlist": null
}
```

- `persist=false`：只返回 chunk 预览（截断），供调试。  
- `persist=true`：写入下游入库队列或直接交给 knowledge worker。  

**输出摘要：**

```json
{
  "ok": true,
  "chunk_count": 128,
  "section_type_hist": {
    "title": 10,
    "specification": 20,
    "parameter": 35,
    "table": 15,
    "faq": 8,
    "review": 12,
    "fallback_window": 0
  },
  "sample_chunks": []
}
```

若 `fallback_window` 占比异常高，返回 warning，提示文档结构识别失败。

## 与 Documents 协作

典型上传路径：

```
documents.upload → parser.detect_type → parser.parse → parser.chunk(persist=true)
  → vector.upsert / kg.write / OpenSearch index（由 knowledge 工具或 worker 完成）
```

Research Agent 对临时网页：

```
crawl.fetch → documents.register(snapshot) → parser.parse → …
```

## 权限

| 权限 | 工具 |
|------|------|
| `parser:read` | detect、list、chunk(persist=false) |
| `parser:write` | parse、reparse、chunk(persist=true) |

## 资源隔离

- 解析在 worker 池执行，MCP server 只投递任务并等待结果（长任务用 progress 事件）。  
- `timeout_ms` 随页数缩放，设硬上限。  
- 内存爆炸类文件标记 `quarantined`。

## 错误码

| code | 含义 |
|------|------|
| `unsupported_type` | 无路由且兜底失败 |
| `encrypted_pdf` | 加密无法解析 |
| `empty_content` | 无可提取文本 |
| `parser_timeout` | 超时 |
| `object_not_found` | MinIO 缺失 |

## 验收

1. PDF/PPTX/HTML 样例分别路由到 Docling/MarkItDown/Unstructured。  
2. `parser=auto` 与显式指定结果一致（在类型正确时）。  
3. 解析产物可被 chunker 消费且 citation 字段可填。  
4. Agent 无需知道 Docling API 细节。
