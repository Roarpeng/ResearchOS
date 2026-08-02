# WebSocket 事件协议

WebSocket 是 ResearchOS 研究过程的主推通道，用于实时展示规划步骤、工具调用、引用、人工中断与终态。HTTP SSE 使用**相同事件 JSON**，仅传输层不同。

## 连接

```
WSS /api/v1/ws/research/{task_id}
```

本地：

```
ws://localhost:8000/api/v1/ws/research/{task_id}
```

### 鉴权握手

连接建立后客户端发送：

```json
{
  "type": "auth",
  "token": "<access_token>",
  "last_seq": 42,
  "protocol": "1"
}
```

成功：

```json
{
  "type": "auth_ok",
  "task_id": "tsk_01H...",
  "server_time": "2026-08-02T01:20:00Z",
  "replayed_from": 42
}
```

失败：关闭连接，关闭码建议：

| Code | 含义 |
|------|------|
| 4401 | 鉴权失败 |
| 4403 | 无任务权限 |
| 4404 | 任务不存在 |
| 4429 | 连接数限流 |

### 心跳

- 服务端每 20s 发送：`{"type":"ping","ts":"..."}`
- 客户端回复：`{"type":"pong","ts":"..."}`
- 60s 无 pong → 服务端断开；客户端应指数退避重连并带上 `last_seq`

## 事件通用信封

除握手与心跳外，业务事件统一为：

```json
{
  "type": "event",
  "schema_version": 1,
  "event_id": "evt_01H...",
  "task_id": "tsk_01H...",
  "seq": 43,
  "event_type": "step.started",
  "ts": "2026-08-02T01:20:01.123Z",
  "payload": {}
}
```

规则：

1. `seq` 在单个 `task_id` 内从 1 起严格递增，无空洞（重放不改序号）
2. 客户端以 `seq` 去重；`last_seq` 续传请求 `seq > last_seq`
3. `event_type` 使用 `domain.action` 点分命名
4. 未知 `event_type` 时前端应忽略或显示通用日志，不得断开

## 客户端 → 服务端消息

| `type` | 说明 |
|--------|------|
| `auth` | 鉴权 |
| `pong` | 心跳应答 |
| `subscribe` | 可选；当前路径已绑定 task，可忽略 |
| `interrupt_intent` | UI 意图预告（非提交）；真正决策走 REST interrupt |
| `client_telemetry` | 可选：渲染延迟等，采样上报 |

业务决策**必须**走 REST `POST .../interrupt`，避免 WS 与 REST 双写状态。

## 服务端事件类型

### 任务生命周期

#### `task.accepted`

任务进入队列。

```json
{
  "status": "queued",
  "mode": "deep"
}
```

#### `task.status`

状态变更。

```json
{
  "status": "researching",
  "previous": "planning",
  "message": "开始证据收集"
}
```

#### `task.completed`

```json
{
  "status": "completed",
  "report_id": "rpt_01H...",
  "duration_ms": 182340
}
```

#### `task.failed`

```json
{
  "status": "failed",
  "error": {
    "code": "UPSTREAM_RUNTIME",
    "message": "Tool browser.timeout"
  },
  "retryable": true
}
```

#### `task.cancelled`

```json
{
  "status": "cancelled",
  "reason": "user_cancelled"
}
```

### 规划与步骤

#### `plan.updated`

Planner 产出或修订计划。

```json
{
  "plan_id": "plan_1",
  "steps": [
    {"id": "s1", "title": "收集厂商规格", "status": "pending"},
    {"id": "s2", "title": "对照 ISO/TS 15066", "status": "pending"}
  ],
  "rationale": "先对齐公开规格再做认证对比"
}
```

#### `step.started` / `step.finished`

```json
{
  "step_id": "s1",
  "title": "收集厂商规格",
  "agent": "research",
  "index": 1
}
```

`step.finished` 额外：

```json
{
  "step_id": "s1",
  "status": "ok",
  "summary": "已获取 3 家公开规格表",
  "duration_ms": 12000
}
```

### 消息与流式文本

#### `message.delta`

增量文本（思考摘要、章节草稿）。前端按 `stream_id` 拼接。

```json
{
  "stream_id": "str_writer_sec1",
  "role": "assistant",
  "delta": "在力控场景下，",
  "format": "markdown"
}
```

#### `message.completed`

```json
{
  "stream_id": "str_writer_sec1",
  "role": "assistant",
  "content": "完整段落...",
  "format": "markdown"
}
```

### 工具调用

#### `tool.started` / `tool.finished`

```json
{
  "tool_call_id": "tc_1",
  "tool": "mcp.search.web",
  "input_preview": {"q": "collaborative robot force limiting"},
  "agent": "research"
}
```

`tool.finished`：

```json
{
  "tool_call_id": "tc_1",
  "tool": "mcp.search.web",
  "ok": true,
  "output_preview": {"n": 8},
  "duration_ms": 2100,
  "artifact_ids": ["art_01H..."]
}
```

敏感参数（密钥、Cookie）不得出现在 `input_preview`。

### 引用与证据

#### `citation.added`

```json
{
  "citation_id": "cit_12",
  "title": "ISO/TS 15066 Overview",
  "url": "https://...",
  "source_type": "standard",
  "snippet": "...",
  "document_id": null,
  "confidence": 0.82
}
```

#### `evidence.updated`

证据库摘要变更（计数或关键结论）。

```json
{
  "evidence_count": 15,
  "claim": "三家均声明支持功率与力限制模式",
  "supporting_citation_ids": ["cit_12", "cit_15"]
}
```

### 人工中断

#### `interrupt.required`

```json
{
  "interrupt_id": "int_01H...",
  "reason": "review_gate",
  "prompt": "是否继续专利深度对比？",
  "options": [
    {"id": "continue_patents", "label": "继续专利对比"},
    {"id": "write_report", "label": "直接写报告"},
    {"id": "abort", "label": "终止"}
  ],
  "timeout_sec": 3600
}
```

前端进入阻塞 UI；用户决策后调用 REST。成功后会收到 `interrupt.resolved`。

#### `interrupt.resolved`

```json
{
  "interrupt_id": "int_01H...",
  "action": "continue_patents",
  "message": "补充欧洲市场"
}
```

### 评审与报告

#### `review.feedback`

```json
{
  "severity": "medium",
  "issues": [
    {"code": "MISSING_CITATION", "message": "选型建议段缺少引用"}
  ],
  "passed": false
}
```

#### `report.ready`

```json
{
  "report_id": "rpt_01H...",
  "title": "...",
  "formats": ["markdown", "pdf"]
}
```

## 缓冲与重放

| 组件 | 职责 |
|------|------|
| Runtime | 产出事件，写入 Redis Stream（或等价） |
| Gateway | 扇出到在线连接；按 `last_seq` 重放 |
| Redis | 每任务保留最近 N 条或 TTL（建议 ≥ 24h / 最多 5000 条） |
| PostgreSQL | 持久化关键状态与可选事件归档 |

重放完成后发送：

```json
{
  "type": "replay_eof",
  "task_id": "tsk_01H...",
  "upto_seq": 120
}
```

之后为实时事件。

## 并发连接

- 同一用户同一任务允许多连接（多标签页）；事件扇出到全部连接
- 建议硬限制：每用户 10 活跃 WS；超额 `4429`

## 前端渲染建议

1. 用 `seq` 排序与去重，不以到达墙钟时间为序
2. `message.delta` 做节流（如 rAF）以免抖动
3. `citation.added` 更新侧栏，不打断主阅读流
4. `interrupt.required` 使用模态或固定底栏，清晰展示可选项
5. 收到 `task.completed` / `report.ready` 后再拉报告全文，避免半成品闪烁

更多 UX 见 [../frontend/01-ux-principles.md](../frontend/01-ux-principles.md)。

## 版本兼容

- `protocol` / `schema_version` 当前为 `1`
- 新增可选字段兼容；删除或改义字段需升版本并在 `auth_ok` 协商
- 服务端可同时理解 `protocol: "1"`；拒识时关闭并提示升级客户端
