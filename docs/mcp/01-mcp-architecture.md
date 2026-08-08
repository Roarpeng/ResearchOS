# 01 — MCP 架构

## 定位

MCP（Model Context Protocol）层把 ResearchOS 的外部能力标准化为 **Tool Server + Tool Schema**。LangGraph Runtime 中的 Agent 通过 MCP Client 发现工具、校验参数、执行调用并回收结构化结果。

```
┌─────────────┐     ┌──────────────────┐     ┌────────────────────┐
│  Agents     │────▶│  MCP Client      │────▶│  MCP Tool Servers  │
│  (LangGraph)│     │  (Runtime 内)    │     │  search / browser  │
└─────────────┘     └──────────────────┘     │  parser / knowledge│
                                             │  report / github   │
                                             │  documents         │
                                             └─────────┬──────────┘
                                                       │
                                             ┌─────────▼──────────┐
                                             │ SearXNG / Tavily   │
                                             │ Brave / Browsers   │
                                             │ MinIO / Neo4j      │
                                             │ Qdrant / OpenSearch│
                                             │ Typst / Pandoc     │
                                             └────────────────────┘
```

## Server 拓扑（推荐）

按域拆分 Server，避免单进程过大；开发环境可合并为 `researchos-mcp` 单体。

| Server 名 | 工具前缀 / 域 | 说明 |
|-----------|---------------|------|
| `mcp-search` | `search.*` | 统一搜索路由 |
| `mcp-browser` | `browser.*` / `crawl.*` | 浏览与爬取 |
| `mcp-parser` | `parser.*` | 文档解析与可选分块 |
| `mcp-knowledge` | `kg.*` / `vector.*` / `knowledge.*` | 图谱与向量与混合检索 |
| `mcp-documents` | `documents.*` | MinIO 文档对象与登记 |
| `mcp-report` | `report.*` | Typst / Pandoc 导出 |
| `mcp-github` | `github.*` | 仓库读写受限操作 |
| `tia-openness` | `tia.*` | TIA Portal Openness（工业 Milestone 1） |

Gateway 或 Runtime 启动时从配置加载 server 列表与 transport（stdio / HTTP / SSE，以部署为准）。

## 工具描述契约

每个工具至少包含：

| 字段 | 说明 |
|------|------|
| `name` | 稳定名称，如 `search.query` |
| `description` | 给模型看的用途说明（含何时不要用） |
| `input_schema` | JSON Schema |
| `output_schema` | 结构化输出（强烈建议） |
| `side_effect` | `none` / `write` / `external_network` / `export` |
| `permission_scope` | 所需权限键 |
| `timeout_ms` | 默认超时 |
| `idempotent` | 是否幂等 |

示例（逻辑）：

```json
{
  "name": "vector.search",
  "side_effect": "none",
  "permission_scope": "vector:read",
  "idempotent": true,
  "timeout_ms": 5000
}
```

## 与 LangGraph 集成

1. **绑定**：Supervisor / Research / Memory 节点在编译图时挂载允许的 tool 子集。  
2. **调用**：模型发 tool call → Runtime 鉴权 → MCP Client 执行 → 观察写回 state（如 `evidence`）。  
3. **人机打断**：高风险 `side_effect=write|export` 可配置 human-in-the-loop。  
4. **流式**：长时 crawl / 导出通过进度事件推送 Gateway WebSocket。  
5. **Checkpoint**：工具结果摘要进入 state；大体量正文进对象存储，state 只留引用 id。

State 中与工具相关的字段建议：

```text
TaskState.evidence[]      # 带 citation 的片段
TaskState.tool_traces[]   # tool_call_id, name, latency, status
TaskState.artifacts[]     # 导出文件、爬取快照 object_key
```

## 统一错误模型

```json
{
  "ok": false,
  "error": {
    "code": "provider_timeout",
    "message": "Tavily timed out",
    "retryable": true,
    "provider": "tavily"
  }
}
```

常见错误码：`permission_denied`、`invalid_argument`、`provider_timeout`、`provider_rate_limit`、`not_found`、`quarantined`、`dependency_unavailable`。

## 路由器模式

若干域提供**门面工具**，内部再路由：

| 门面 | 路由目标 |
|------|----------|
| `search.query` | SearXNG / Tavily / Brave |
| `parser.parse` | Docling / MarkItDown / Unstructured |
| `knowledge.retrieve` | Graph + Vector + BM25 融合 |
| `report.export` | Typst 或 Pandoc 管线 |

门面负责：参数归一化、提供商选择、降级、统一输出 schema。Agent 默认只见门面；调试权限可暴露 `*.raw_*` 底层工具。

## Documents 与 GitHub（交叉能力）

### documents

- `documents.upload` / `documents.get` / `documents.list`  
- `documents.open_text`（小文件）  
- 与入库流水线衔接：upload → ingestion  

### github

- 读：仓库树、文件内容、issue / PR 元数据（只读默认）  
- 写：仅在显式权限下创建 issue 评论或受限提交（默认关闭）  
- 研究场景主要用于规范、README、设计文档摄取  

二者结果可进入 `documents` → parser → knowledge，与 Web 来源共用 IR。

## 配置与发现

```yaml
mcp:
  servers:
    - name: mcp-search
      transport: http
      url: http://mcp-search:8080
    - name: mcp-knowledge
      transport: http
      url: http://mcp-knowledge:8080
  agent_allowlist:
    research: [search.*, browser.*, crawl.*, documents.*, parser.*, knowledge.retrieve, vector.search, kg.query]
    memory: [kg.*, vector.*, knowledge.*, documents.*, parser.*]
    writer: [knowledge.retrieve, vector.search, kg.query, report.*, documents.get]
    planner: [knowledge.retrieve, search.query]
```

## 可观测性

- Trace：每个 tool call 关联 `task_id` / `agent_name`。  
- Metrics：`mcp_tool_calls_total{tool,status}`、`mcp_tool_latency_ms`。  
- 审计：写操作记 actor、workspace、参数摘要（脱敏）。  

## 非目标

- MCP 层不内嵌 Supervisor 业务策略（那是 Agent 的职责）。  
- 不在工具内直接调用「随意 SQL / Cypher 字符串」给不可信 Agent（需参数化 query API）。  
- 不替代 LiteLLM；模型调用仍走 AI Gateway。
