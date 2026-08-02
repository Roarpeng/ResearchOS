# ResearchOS API 文档

ResearchOS API 以 FastAPI Gateway 为统一入口，对外提供认证、会话、研究任务、知识库与实时流式事件能力。本文档集描述架构阶段约定的契约；实现阶段应以此为接口基准，并通过 OpenAPI 与集成测试对齐。

## 文档索引

| 文档 | 内容 |
|------|------|
| [01-gateway-overview.md](./01-gateway-overview.md) | Gateway 职责、分层、路由约定与错误模型 |
| [02-auth-and-sessions.md](./02-auth-and-sessions.md) | 认证、会话、令牌与权限边界 |
| [03-research-api.md](./03-research-api.md) | 创建研究任务、流式事件、获取报告 |
| [04-knowledge-api.md](./04-knowledge-api.md) | 文档入库、检索、图谱与知识空间 |
| [05-websocket-events.md](./05-websocket-events.md) | WebSocket 事件协议、载荷与重连 |

## 设计目标

1. **单一入口**：客户端只对接 Gateway；Runtime、Agent、MCP、Knowledge 均不直接暴露给浏览器。
2. **流式优先**：研究过程以 WebSocket（主）/ SSE（备）推送步骤、引用与中间结论。
3. **可恢复**：任务与会话绑定 checkpoint，断线后可按 `task_id` 恢复事件与状态。
4. **模型无关**：LLM 调用经 LiteLLM，API 不绑定具体供应商字段。
5. **私有部署友好**：鉴权、对象存储与知识库均可完全内网运行。

## 基础约定

### Base URL

```
https://{host}/api/v1
```

本地开发默认：

```
http://localhost:8000/api/v1
```

### 内容类型

- 请求体：`application/json`（文件上传使用 `multipart/form-data`）
- 响应体：`application/json`
- WebSocket：文本帧，JSON 编码事件

### 公共请求头

| Header | 必填 | 说明 |
|--------|------|------|
| `Authorization` | 是（公开健康检查除外） | `Bearer <access_token>` |
| `X-Request-Id` | 否 | 客户端追踪 ID；未提供时 Gateway 生成 |
| `X-Workspace-Id` | 条件 | 多工作空间场景下指定知识/任务作用域 |

### 公共响应信封

成功：

```json
{
  "ok": true,
  "data": {},
  "meta": {
    "request_id": "req_...",
    "ts": "2026-08-02T01:00:00Z"
  }
}
```

失败：

```json
{
  "ok": false,
  "error": {
    "code": "AUTH_INVALID_TOKEN",
    "message": "Access token is invalid or expired",
    "details": {}
  },
  "meta": {
    "request_id": "req_...",
    "ts": "2026-08-02T01:00:00Z"
  }
}
```

### 资源标识

| 前缀 | 含义 |
|------|------|
| `usr_` | 用户 |
| `ses_` | 会话 |
| `tsk_` | 研究任务 |
| `rpt_` | 报告 |
| `doc_` | 文档 |
| `kb_` | 知识空间 |
| `evt_` | 事件 |

## 主要资源一览

```
/auth/*          登录、刷新、登出
/sessions/*      会话生命周期
/research/*      研究任务与报告
/knowledge/*     文档、检索、图谱
/ws/*            WebSocket 流
/health          存活与依赖探活
```

## 与内部组件的关系

```
Client
  │  HTTPS / WSS
  ▼
FastAPI Gateway  ──► PostgreSQL（用户、会话、任务元数据）
  │                  Redis（会话缓存、事件缓冲、限流）
  ├──► LangGraph Runtime（执行、checkpoint、interrupt）
  ├──► Knowledge Layer（Qdrant / Neo4j / OpenSearch / MinIO）
  └──► LiteLLM（模型调用，不经客户端直连）
```

n8n **不**参与研究推理链路；仅用于可选的定时触发与通知投递（邮件/Webhook/IM）。详见部署文档。

## 版本策略

- 当前文档版本：`v1`（架构契约）
- 破坏性变更必须升主版本（`/api/v2`）并保留至少一个小版本的弃用窗口
- 新增可选字段视为向后兼容

## 实现状态

当前仓库处于 **Architecture Phase**。本文档定义目标契约；代码落地时应同步更新 OpenAPI（`/openapi.json`）与本目录示例，避免文档漂移。
