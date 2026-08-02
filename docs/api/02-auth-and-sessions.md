# 认证与会话

ResearchOS Gateway 使用 **Bearer Access Token + Refresh Token** 作为默认人机认证，并支持 **API Key** 供服务间或自动化调用。会话（Session）将用户、工作空间与研究上下文绑定，是流式通道与任务归属的锚点。

## 认证模式

| 模式 | 适用 | 凭证 |
|------|------|------|
| 用户登录（密码 / OIDC） | Web 控制台 | Access + Refresh JWT |
| API Key | SDK、CI、内部服务 | `ros_ak_...` 静态密钥 |
| 服务账号（后期） | 批处理 / 工业桥接 | 短期 JWT，作用域受限 |

架构阶段先落地本地账号 + API Key；OIDC（企业 IdP）作为私有部署扩展。

## 令牌模型

### Access Token

- 类型：JWT（HS256 或 RS256，私有部署推荐 RS256）
- 默认 TTL：15–60 分钟（可配）
- Claims：

```json
{
  "sub": "usr_01H...",
  "sid": "ses_01H...",
  "wid": "ws_01H...",
  "scopes": ["research:write", "knowledge:read"],
  "typ": "access",
  "exp": 1730000000,
  "iat": 1729996400,
  "jti": "jti_..."
}
```

### Refresh Token

- 不透明随机串或长寿命 JWT，仅用于 `/auth/refresh`
- 默认 TTL：7–30 天
- 存储于 PostgreSQL（哈希）与可选 Redis 黑名单
- 刷新时轮换（rotation）：旧 refresh 立即失效

### API Key

- 明文仅创建时返回一次；库中存哈希
- Header：`Authorization: Bearer ros_ak_...` 或 `X-API-Key: ros_ak_...`
- 绑定工作空间与 scopes；无 `sid`（会话可选自动创建 ephemeral session）

## 端点

### 登录

`POST /api/v1/auth/login`

```json
{
  "email": "user@example.com",
  "password": "********",
  "workspace_id": "ws_01H..." 
}
```

`workspace_id` 可选；省略时使用用户默认工作空间。

响应：

```json
{
  "ok": true,
  "data": {
    "access_token": "eyJ...",
    "refresh_token": "rt_...",
    "token_type": "bearer",
    "expires_in": 1800,
    "session": {
      "id": "ses_01H...",
      "workspace_id": "ws_01H...",
      "user_id": "usr_01H..."
    }
  }
}
```

失败：`401 AUTH_INVALID_CREDENTIALS`（不区分邮箱是否存在，防枚举）。

### 刷新

`POST /api/v1/auth/refresh`

```json
{
  "refresh_token": "rt_..."
}
```

成功返回新的 access + refresh；若 refresh 已被轮换或吊销 → `401 AUTH_INVALID_TOKEN`。

### 登出

`POST /api/v1/auth/logout`

```json
{
  "refresh_token": "rt_...",
  "all_sessions": false
}
```

- `all_sessions=false`：吊销当前 refresh 与对应 session
- `all_sessions=true`：吊销该用户全部会话（安全事件 / 改密后）

Access JWT 在过期前仍可能有效；Gateway 通过 Redis `jti` 黑名单（可选）立即失效。

### 当前主体

`GET /api/v1/auth/me`

返回用户资料、默认工作空间、scopes。

### API Key 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/auth/api-keys` | 创建；响应含一次性明文 |
| `GET` | `/api/v1/auth/api-keys` | 列出（无明文） |
| `DELETE` | `/api/v1/auth/api-keys/{key_id}` | 吊销 |

创建请求示例：

```json
{
  "name": "ci-ingest",
  "workspace_id": "ws_01H...",
  "scopes": ["knowledge:write", "knowledge:read"],
  "expires_at": null
}
```

## 会话（Session）

会话是一次「用户在某工作空间内的交互上下文」，用于：

- 绑定后续研究任务的默认归属
- 关联 WebSocket 连接的鉴权主体
- 记录 UI 偏好与最近任务列表游标（可选）

### 生命周期

```
login / create session
    │
    ▼
 active ──► 创建任务、订阅 WS、刷新活动时间
    │
    ├── logout / TTL 到期 ──► closed
    └── 安全吊销 ──► revoked
```

### 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/sessions` | 显式创建会话（已登录主体切换工作空间时） |
| `GET` | `/api/v1/sessions/current` | 当前会话 |
| `GET` | `/api/v1/sessions` | 列出会话（管理） |
| `DELETE` | `/api/v1/sessions/{session_id}` | 关闭会话 |

创建请求：

```json
{
  "workspace_id": "ws_01H...",
  "label": "竞品分析会话",
  "client": {
    "type": "web",
    "user_agent": "..."
  }
}
```

响应核心字段：

```json
{
  "id": "ses_01H...",
  "workspace_id": "ws_01H...",
  "user_id": "usr_01H...",
  "status": "active",
  "created_at": "2026-08-02T01:00:00Z",
  "expires_at": "2026-08-03T01:00:00Z",
  "last_seen_at": "2026-08-02T01:05:00Z"
}
```

### 会话与研究任务

- 创建研究任务时，若请求未带 `session_id`，使用 access token 中的 `sid`
- 任务元数据持久化 `session_id` + `workspace_id` + `user_id`
- WebSocket 订阅校验：连接主体必须对 `task_id` 所属工作空间有读权限

## 权限（Scopes）

| Scope | 能力 |
|-------|------|
| `research:read` | 查看任务、事件、报告 |
| `research:write` | 创建任务、发送 interrupt、取消 |
| `knowledge:read` | 检索、读文档元数据 |
| `knowledge:write` | 上传、删除、重建索引 |
| `admin:workspace` | 成员与 API Key 管理 |

缺省用户角色映射：

- `member` → `research:*` + `knowledge:read`（写知识需显式授权）
- `editor` → `research:*` + `knowledge:*`
- `admin` → 全部 + `admin:workspace`

Gateway 在路由层用依赖注入校验 scopes；资源层再校验工作空间成员关系。

## WebSocket 鉴权

推荐流程：

1. 客户端建立 `wss://host/api/v1/ws/research/{task_id}`
2. 连接成功后 **3 秒内** 发送：

```json
{
  "type": "auth",
  "token": "<access_token>",
  "last_seq": 0
}
```

3. 服务端校验 token + 任务权限，回复 `auth_ok` 或关闭连接（`4401`）
4. 可选：query `?token=` 仅用于无法发首帧的环境，生产默认关闭

`last_seq` 用于断线续传：Gateway 从 Redis 事件缓冲重放 `seq > last_seq` 的事件。

## 安全要求

1. **密钥**：`JWT_SECRET` / RSA 私钥仅存在于 Gateway；禁止写入前端包。
2. **传输**：生产强制 HTTPS/WSS；本地可用 HTTP。
3. **密码**：Argon2id 或 bcrypt；禁止明文日志。
4. **暴力破解**：登录失败按 IP + 邮箱限流；触发后返回 `429`。
5. **审计**：登录、刷新失败、API Key 创建/吊销、会话全局登出写入审计表。
6. **多租户**：所有数据查询强制 `workspace_id` 过滤；禁止跨空间 IDOR。

## 与前端的约定

- Access token 存内存或安全存储；Refresh 用 HttpOnly Secure Cookie（Web）或安全存储（桌面/SDK）
- 401 时尝试 refresh 一次；仍失败则清会话并跳转登录
- 流式页在 token 临近过期时静默刷新，避免长任务中途断流

## 数据存储

| 数据 | 存储 |
|------|------|
| 用户、密码哈希、工作空间成员 | PostgreSQL |
| Refresh token 哈希、API Key 哈希 | PostgreSQL |
| Session 热状态、jti 黑名单、限流 | Redis |
| 审计日志 | PostgreSQL（可归档对象存储） |
