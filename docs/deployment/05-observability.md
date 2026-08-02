# 可观测性

可观测性覆盖 **日志、指标、追踪、健康检查与告警**，使研究长任务可诊断、可审计、可容量规划。架构阶段定义信号约定；实现阶段接入具体后端（如 Loki/Prometheus/Tempo/OpenTelemetry Collector）。

## 目标信号

| 信号 | 用途 |
|------|------|
| 日志 | 排障、审计关联、安全事件 |
| 指标 | SLO、限流、队列堆积、模型延迟 |
| 追踪 | 跨 Gateway → Runtime → MCP → LiteLLM 的一次任务链路 |
| 健康 | 编排探活与依赖降级 |
| 告警 | 人机响应（可经 n8n 发通知，但不经 n8n 做推理） |

## 关联 ID

每个请求与任务必须可关联：

| ID | 注入点 | 传播 |
|----|--------|------|
| `request_id` | Gateway 中间件 | 日志字段、响应 `meta`、追踪 baggage |
| `task_id` | 创建研究任务 | Runtime、事件、Worker |
| `session_id` / `user_id` / `workspace_id` | 鉴权后 | 日志与审计（注意脱敏） |
| `tool_call_id` | Agent 工具调用 | MCP 与上游 HTTP |

禁止在日志中输出：密码、Bearer token 全文、MinIO 密钥、文档正文全量（可记 hash / 长度 / 前 N 字符开关）。

## 日志规范

结构化 JSON（示例字段）：

```json
{
  "ts": "2026-08-02T01:30:00Z",
  "level": "INFO",
  "service": "gateway",
  "msg": "research.task.created",
  "request_id": "req_...",
  "task_id": "tsk_...",
  "workspace_id": "ws_...",
  "user_id": "usr_...",
  "duration_ms": 42
}
```

级别约定：

- `DEBUG`：开发细节、事件扇出
- `INFO`：生命周期（创建任务、完成、中断）
- `WARN`：可恢复上游抖动、降级
- `ERROR`：失败终态、依赖不可用
- `AUDIT`：安全相关（可映射为独立 sink）

## 指标（Prometheus 风格命名）

### Gateway

| 指标 | 类型 | 说明 |
|------|------|------|
| `ros_http_requests_total` | counter | 按 method/path/status |
| `ros_http_request_duration_seconds` | histogram | 延迟 |
| `ros_ws_connections` | gauge | 活跃 WS |
| `ros_ws_events_total` | counter | 推送事件按 `event_type` |
| `ros_auth_failures_total` | counter | 鉴权失败 |
| `ros_rate_limited_total` | counter | 限流 |

### Runtime

| 指标 | 类型 | 说明 |
|------|------|------|
| `ros_tasks_active` | gauge | 运行中任务 |
| `ros_tasks_total` | counter | 按 status 终态 |
| `ros_task_duration_seconds` | histogram | 任务耗时 |
| `ros_interrupt_waiting` | gauge | 等待人工中断数 |
| `ros_tool_calls_total` | counter | 按 tool/ok |
| `ros_tool_duration_seconds` | histogram | 工具耗时 |

### Knowledge

| 指标 | 类型 | 说明 |
|------|------|------|
| `ros_ingest_jobs_active` | gauge | 入库作业 |
| `ros_ingest_duration_seconds` | histogram | 入库耗时 |
| `ros_search_duration_seconds` | histogram | 检索耗时按 mode |
| `ros_search_hits` | histogram | 命中数分布 |

### LiteLLM / 模型

| 指标 | 类型 | 说明 |
|------|------|------|
| `ros_llm_requests_total` | counter | 按 model_profile |
| `ros_llm_tokens_total` | counter | prompt/completion |
| `ros_llm_errors_total` | counter | 按错误类 |
| `ros_llm_latency_seconds` | histogram | 模型延迟 |

若 LiteLLM 自带指标，可 scrape 后用 recording rule 映射到 `ros_*` 前缀。

## 分布式追踪

使用 OpenTelemetry：

- Gateway 创建 root span：`HTTP POST /research/tasks`
- Runtime 子 span：`graph.run`、`node.planner`、`node.research`、`tool.mcp.*`
- LiteLLM 客户端 span：`llm.completion`
- Knowledge：`ingest.parse`、`search.hybrid`

采样：生产默认头采样 5–10%；错误与慢任务强制保留。

## 健康与就绪

| 端点 | 用途 |
|------|------|
| `GET /api/v1/health/live` | 进程活着 |
| `GET /api/v1/health/ready` | 依赖就绪 |

编排：

- `livenessProbe` → live
- `readinessProbe` → ready
- 依赖降级：可选组件失败标记 `degraded`，核心仍 ready（见 API Gateway 文档）

## 仪表盘建议

1. **总览**：任务创建/完成/失败率、P95 任务时长、WS 连接数
2. **模型**：token 消耗、错误率、按 profile 延迟
3. **知识**：入库队列深度、检索 P95、Qdrant/Neo4j 健康
4. **安全**：登录失败突增、429 突增、权限拒绝

## 告警基线

| 条件 | 级别 | 说明 |
|------|------|------|
| `ready` 连续失败 2m | critical | 入口不可用 |
| 任务失败率 > 10%（15m） | high | Runtime/工具异常 |
| LLM 错误率 > 5%（10m） | high | 密钥/配额/Ollama |
| 入库作业堆积 > 阈值 | medium | Worker 不足 |
| 磁盘 / 卷使用 > 85% | high | MinIO/PG/向量 |
| 证书到期 < 14d | medium | TLS |

通知通道可由 Alertmanager → webhook → **n8n** 发 IM/邮件；保持「n8n 只通知」边界。

## 本地开发

最小可观测：

- 容器 `stdout` JSON 日志 + `docker compose logs -f gateway runtime`
- Gateway `/metrics`（实现阶段）可用 Prometheus 单容器 scrape
- 无需一上来上完整 EFK

## 隐私

- 默认日志不含用户问题全文；可通过 `LOG_QUERY_TEXT=false` 控制
- 追踪属性避免存放整篇文档
- 私有化环境观测栈同驻 VPC，不默认推送厂商云

## 与架构阶段文档的关系

实现 PR 在引入 Gateway/Runtime 骨架时，应同步：

1. 输出 `request_id`
2. 暴露 `/metrics` 或 OTel exporter 配置项
3. 健康检查端点

未达上述最低线的「可运行 Demo」可接受，但不得称为生产就绪。
