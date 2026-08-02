# 研究 API

研究 API 覆盖「创建任务 → 流式执行 → 人工中断 → 获取报告」全链路。执行细节在 LangGraph Runtime；Gateway 负责鉴权、任务元数据与事件扇出。

## 概念

| 概念 | 说明 |
|------|------|
| Task | 一次研究请求的持久化实体（`tsk_`） |
| Run | Task 的一次执行实例；支持失败后重跑（架构预留） |
| Event | 执行过程中的有序事件（`seq` 单调递增） |
| Report | 终态产物：Markdown/结构化章节 + 引用 + 附件 |
| Interrupt | 人工介入点：暂停、补充指令、批准/拒绝 |

典型状态机：

```
queued → planning → researching → reviewing → writing → completed
                ↘                ↘
              interrupted      failed / cancelled
```

## 创建研究任务

`POST /api/v1/research/tasks`

### 请求

```json
{
  "query": "对比三家协作机器人厂商在力控与安全认证上的差异，并给出选型建议",
  "workspace_id": "ws_01H...",
  "session_id": "ses_01H...",
  "mode": "deep",
  "options": {
    "language": "zh-CN",
    "max_steps": 24,
    "enable_web": true,
    "enable_knowledge": true,
    "citation_required": true,
    "report_format": ["markdown", "pdf"],
    "model_profile": "default",
    "human_interrupt": "on_review"
  },
  "context": {
    "knowledge_space_ids": ["kb_01H..."],
    "seed_urls": [],
    "constraints": ["优先公开标准与技术白皮书"]
  }
}
```

字段说明：

| 字段 | 必填 | 说明 |
|------|------|------|
| `query` | 是 | 研究问题，1–8000 字符 |
| `workspace_id` | 否 | 默认取会话工作空间 |
| `session_id` | 否 | 默认取 token `sid` |
| `mode` | 否 | `quick` \| `deep` \| `industrial`；默认 `deep` |
| `options.language` | 否 | 报告语言 |
| `options.max_steps` | 否 | 硬上限，防止失控循环 |
| `options.enable_web` | 否 | 是否允许联网 MCP 工具 |
| `options.enable_knowledge` | 否 | 是否检索企业知识库 |
| `options.citation_required` | 否 | 终稿强制引用 |
| `options.report_format` | 否 | `markdown` / `pdf` / `docx`（PDF/DOCX 依赖 Gotenberg/Typst） |
| `options.model_profile` | 否 | LiteLLM 路由配置名 |
| `options.human_interrupt` | 否 | `never` \| `on_review` \| `always_plan` |
| `context.knowledge_space_ids` | 否 | 限定知识空间 |
| `context.seed_urls` | 否 | 种子 URL |
| `context.constraints` | 否 | 自然语言约束 |

### 响应 `201`

```json
{
  "ok": true,
  "data": {
    "id": "tsk_01H...",
    "status": "queued",
    "query": "...",
    "mode": "deep",
    "created_at": "2026-08-02T01:10:00Z",
    "stream": {
      "ws_url": "/api/v1/ws/research/tsk_01H...",
      "sse_url": "/api/v1/research/tasks/tsk_01H.../events"
    }
  }
}
```

创建后 Runtime 异步拉起图执行；客户端应立刻连接 WS（或 SSE）。

## 查询任务

### 列表

`GET /api/v1/research/tasks?workspace_id=ws_...&status=completed&limit=20&cursor=...`

### 详情

`GET /api/v1/research/tasks/{task_id}`

```json
{
  "ok": true,
  "data": {
    "id": "tsk_01H...",
    "status": "researching",
    "query": "...",
    "mode": "deep",
    "progress": {
      "phase": "researching",
      "step": 7,
      "max_steps": 24,
      "message": "正在交叉验证力控规格书"
    },
    "interrupt": null,
    "report_id": null,
    "error": null,
    "created_at": "...",
    "updated_at": "..."
  }
}
```

当 `status=interrupted` 时，`interrupt` 非空：

```json
{
  "interrupt": {
    "id": "int_01H...",
    "reason": "review_gate",
    "prompt": "请确认是否继续深入专利对比，或直接生成选型报告",
    "options": ["continue_patents", "write_report", "abort"],
    "created_at": "..."
  }
}
```

## 流式事件（HTTP 降级）

`GET /api/v1/research/tasks/{task_id}/events`

- `Accept: text/event-stream`
- Query：`last_seq=0`
- 每条 SSE `data:` 为一完整事件 JSON（与 WS 同 schema）
- 心跳：注释行 `: ping` 每 15s

生产环境优先 WebSocket；SSE 用于受限网络或简单脚本。

事件 schema 见 [05-websocket-events.md](./05-websocket-events.md)。

## 人工中断与恢复

### 提交中断响应

`POST /api/v1/research/tasks/{task_id}/interrupt`

```json
{
  "interrupt_id": "int_01H...",
  "action": "continue_patents",
  "message": "补充欧洲市场 CE/ISO 维度",
  "payload": {}
}
```

| `action` | 含义 |
|----------|------|
| 与 `options` 枚举一致 | 选择预定义分支 |
| `resume` | 通用继续（带 `message` 补充指令） |
| `cancel` | 取消任务 |

成功：`200`，任务回到 `planning`/`researching`/`writing` 等；失败冲突：`409 CONFLICT_INVALID_STATE`。

### 主动请求暂停

`POST /api/v1/research/tasks/{task_id}/pause`

在安全点插入 interrupt；若不支持当前相位，返回 `409`。

### 取消

`POST /api/v1/research/tasks/{task_id}/cancel`

```json
{ "reason": "user_cancelled" }
```

终态 `cancelled`；已生成的部分证据保留只读。

## 获取报告

报告在任务 `completed` 后可用；部分实现可在 `writing` 阶段提供草稿预览。

### 元数据

`GET /api/v1/research/tasks/{task_id}/report`

```json
{
  "ok": true,
  "data": {
    "id": "rpt_01H...",
    "task_id": "tsk_01H...",
    "title": "协作机器人力控与安全认证对比",
    "status": "final",
    "formats": {
      "markdown": "/api/v1/research/reports/rpt_01H.../content?format=markdown",
      "pdf": "/api/v1/research/reports/rpt_01H.../content?format=pdf",
      "json": "/api/v1/research/reports/rpt_01H.../content?format=json"
    },
    "citation_count": 18,
    "created_at": "...",
    "updated_at": "..."
  }
}
```

任务未完成：`409 CONFLICT_REPORT_NOT_READY`。

### 内容

`GET /api/v1/research/reports/{report_id}/content?format=markdown`

- `format=markdown`：`text/markdown` 或 JSON 包一层 `content`
- `format=json`：结构化报告

结构化 JSON 示例：

```json
{
  "title": "...",
  "summary": "...",
  "sections": [
    {
      "id": "sec_1",
      "heading": "执行摘要",
      "markdown": "...",
      "citations": ["cit_1", "cit_2"]
    }
  ],
  "citations": [
    {
      "id": "cit_1",
      "title": "ISO/TS 15066",
      "url": "https://...",
      "source_type": "standard",
      "snippet": "...",
      "retrieved_at": "..."
    }
  ],
  "appendix": {
    "method": "deep research with hybrid GraphRAG",
    "models": ["model_profile:default"],
    "limitations": []
  }
}
```

### 导出文件

`GET /api/v1/research/reports/{report_id}/content?format=pdf`

- 通过 MinIO 预签名 URL 重定向，或 Gateway 代理流式下载
- 生成失败时回退仅提供 Markdown，并在 `formats.pdf` 标为 `null`

## 证据与引用查询

`GET /api/v1/research/tasks/{task_id}/citations`

返回任务过程中累积的引用列表（含未进入终稿的候选）。用于前端引用面板与调试。

`GET /api/v1/research/tasks/{task_id}/artifacts`

返回中间产物：计划书、笔记、工具原始结果指针（MinIO object keys）。大对象不内联。

## 模式差异

| Mode | 行为 |
|------|------|
| `quick` | 少步数、弱反思、适合事实速查 |
| `deep` | Planner → 多轮 Research → Reviewer → Writer；默认 |
| `industrial` | 启用工业 MCP（PLC/ROS2/CAD 等知识与工具约束）；Phase 5 |

## 错误码（研究域）

| code | 含义 |
|------|------|
| `VALIDATION_QUERY_EMPTY` | 空问题 |
| `PERM_WORKSPACE` | 无工作空间权限 |
| `NOT_FOUND_TASK` | 任务不存在 |
| `CONFLICT_INVALID_STATE` | 状态不允许该动作 |
| `CONFLICT_REPORT_NOT_READY` | 报告未就绪 |
| `UPSTREAM_RUNTIME` | Runtime 调用失败 |
| `RATE_TASK_CREATE` | 创建配额耗尽 |

## 客户端推荐流程

```
1. POST /research/tasks
2. 连接 WS /api/v1/ws/research/{task_id}，发送 auth + last_seq
3. 渲染 step / citation / message 事件
4. 若收到 interrupt.required → 展示决策 UI → POST interrupt
5. 收到 task.completed → GET report + content
6. 断线时记录 last_seq，重连重放
```

前端交互细节见 [../frontend/01-ux-principles.md](../frontend/01-ux-principles.md)。
