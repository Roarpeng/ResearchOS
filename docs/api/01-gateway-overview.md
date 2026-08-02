# Gateway 概览

FastAPI Gateway 是 ResearchOS 的唯一对外 API 边界。它负责鉴权、会话、路由、流式推送与对外错误归一，不承载深度研究推理逻辑。

## 职责边界

### Gateway 负责

| 职责 | 说明 |
|------|------|
| 认证与鉴权 | JWT / API Key 校验、工作空间权限 |
| 会话管理 | 创建、续期、绑定用户与任务上下文 |
| API 路由 | REST 资源 CRUD 与动作端点 |
| 流式通道 | WebSocket 主通道；可选 SSE 降级 |
| 请求校验 | Pydantic 模型校验、配额与限流入口 |
| 编排转发 | 将已鉴权请求转发到 Runtime / Knowledge |
| 可观测性 | `request_id`、结构化日志、指标埋点 |

### Gateway 不负责

- Agent 规划、反思与多步推理（→ LangGraph Runtime）
- 向量/图谱检索实现细节（→ Knowledge Layer）
- 模型供应商协议适配（→ LiteLLM）
- 定时调度与外部通知（→ 可选 n8n）
- 文档解析与嵌入流水线执行（→ Knowledge workers）

## 进程与模块布局（目标）

```
gateway/
├── app/
│   ├── main.py              # FastAPI 应用工厂
│   ├── deps.py              # 依赖注入（DB、Redis、Auth）
│   ├── middleware/          # 请求 ID、CORS、限流、审计
│   ├── routers/
│   │   ├── auth.py
│   │   ├── sessions.py
│   │   ├── research.py
│   │   ├── knowledge.py
│   │   └── health.py
│   ├── ws/
│   │   ├── manager.py       # 连接管理
│   │   └── events.py        # 事件编解码
│   ├── services/            # 对 Runtime / Knowledge 的客户端
│   └── schemas/             # 请求/响应模型
└── tests/
```

## 请求生命周期

```
1. 接收 HTTP/WS
2. 中间件：生成 request_id、记录入口日志
3. 鉴权：解析 Bearer / API Key → 主体与权限
4. 路由：校验 body/query → 业务服务
5. 服务：写 PostgreSQL 元数据；必要时调用 Runtime
6. 若为研究任务：订阅 Runtime 事件流并扇出到 WS
7. 返回 REST 响应或持续推送 WS 事件
```

## 路由约定

| 前缀 | 模块 | 说明 |
|------|------|------|
| `/api/v1/auth` | 认证 | 登录、刷新、登出、API Key |
| `/api/v1/sessions` | 会话 | 会话 CRUD 与绑定 |
| `/api/v1/research` | 研究 | 任务、流、报告、中断 |
| `/api/v1/knowledge` | 知识 | 入库、检索、图谱查询 |
| `/api/v1/ws` | WebSocket | `/api/v1/ws/research/{task_id}` |
| `/api/v1/health` | 健康 | liveness / readiness |

## 与 Runtime 的通信

Gateway 对 Runtime 使用内部 gRPC 或 HTTP（实现阶段二选一，推荐异步 HTTP + Redis Streams 作为事件总线）：

```
Gateway ── create_run(task) ──► Runtime
Gateway ── subscribe(run_id) ──► Redis Stream / WS bridge
Runtime ── publish(event)   ──► Redis Stream
Gateway ── fanout(event)    ──► Client WebSocket
```

事件至少包含：`task_id`、`event_type`、`seq`、`payload`、`ts`。详见 [05-websocket-events.md](./05-websocket-events.md)。

## 错误模型

| HTTP | `error.code` 前缀 | 场景 |
|------|-------------------|------|
| 400 | `VALIDATION_` | 参数非法 |
| 401 | `AUTH_` | 未登录或令牌无效 |
| 403 | `PERM_` | 无工作空间/资源权限 |
| 404 | `NOT_FOUND_` | 资源不存在 |
| 409 | `CONFLICT_` | 状态冲突（如任务已终态） |
| 429 | `RATE_` | 限流 |
| 502 | `UPSTREAM_` | Runtime / Knowledge / LiteLLM 失败 |
| 503 | `DEP_` | 依赖不可用（DB/Redis 等） |

所有错误响应使用统一信封（见 [README.md](./README.md)），禁止向客户端泄露内部堆栈。

## 限流与配额（架构约定）

| 维度 | 默认建议 | 存储 |
|------|----------|------|
| 每用户 REST | 120 req/min | Redis 滑动窗口 |
| 每用户创建研究任务 | 20/hour | Redis + PostgreSQL 计数 |
| 每连接 WS 消息入站 | 30/min | 连接本地 + Redis |
| 单任务并发 | 1 个 active run（默认可配置） | Runtime 锁 |

超额返回 `429 RATE_LIMITED`，并在响应头给出 `Retry-After`。

## CORS 与安全头

- 允许来源由 `CORS_ORIGINS` 配置；私有部署默认仅内网前端源
- 启用 `X-Content-Type-Options: nosniff`、`Referrer-Policy: no-referrer` 等基线头
- WebSocket 鉴权：连接时带 `token` query 或首帧 `auth` 消息（推荐首帧，避免令牌进访问日志）

## 健康检查

### `GET /api/v1/health/live`

进程存活。不检查依赖。返回 `200 {"status":"ok"}`。

### `GET /api/v1/health/ready`

依赖就绪：PostgreSQL、Redis、以及配置为必需的 MinIO/Qdrant/Neo4j/LiteLLM。任一必需依赖失败返回 `503`。

```json
{
  "status": "ready",
  "checks": {
    "postgres": "ok",
    "redis": "ok",
    "minio": "ok",
    "qdrant": "ok",
    "neo4j": "ok",
    "litellm": "ok"
  }
}
```

可选组件（OpenSearch、Ollama、n8n、Gotenberg）失败时标记为 `degraded`，不阻塞 ready（除非部署配置将其设为必需）。

## 配置入口

Gateway 读取环境变量（或挂载的 `.env`），关键项：

- `DATABASE_URL`、`REDIS_URL`
- `JWT_SECRET`、`JWT_TTL_SECONDS`
- `RUNTIME_BASE_URL`、`LITELLM_BASE_URL`
- `CORS_ORIGINS`、`LOG_LEVEL`

完整列表见 [部署配置](../deployment/02-configuration.md)。

## 演进原则

1. Gateway 保持薄：新增业务能力优先落在 Runtime / Knowledge / MCP，再经 Gateway 暴露。
2. 对外契约稳定：字段更名视为破坏性变更。
3. 流式协议版本化：事件 schema 带 `schema_version`，便于前端渐进升级。
