# 配置指南

ResearchOS 配置遵循：**环境变量注入密钥、挂载文件承载结构化配置、Compose profiles 控制可选组件**。禁止把密钥写入镜像层或前端包。

## 配置分层

| 层 | 载体 | 内容 |
|----|------|------|
| 密钥与连接串 | `.env` / Secret Manager | 密码、API Key、JWT |
| 服务配置 | `configs/*.yaml` | LiteLLM 路由、模型档位 |
| 运行时特性开关 | 环境变量 | 功能 flag、限流、TTL |
| 前端公开变量 | `NEXT_PUBLIC_*` | 仅 API/WS 基址等非敏感项 |

加载顺序（Gateway / Runtime）：进程环境 → `.env` 文件 → 默认值。未知变量应告警而非静默忽略（实现阶段）。

## 必备环境变量

### 数据面

| 变量 | 示例 | 说明 |
|------|------|------|
| `POSTGRES_PASSWORD` | 强随机 | DB 密码 |
| `DATABASE_URL` | `postgresql+asyncpg://researchos:***@postgres:5432/researchos` | 应用连接 |
| `REDIS_URL` | `redis://redis:6379/0` | 缓存与事件 |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | — | MinIO root |
| `MINIO_ENDPOINT` | `minio:9000` | 内网 endpoint |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | — | 应用专用密钥（非 root 更佳） |
| `MINIO_BUCKET_DOCUMENTS` | `ros-documents` | 文档桶 |
| `MINIO_BUCKET_REPORTS` | `ros-reports` | 报告桶 |
| `QDRANT_URL` | `http://qdrant:6333` | 向量 |
| `NEO4J_URI` | `bolt://neo4j:7687` | 图谱 |
| `NEO4J_USER` / `NEO4J_PASSWORD` | `neo4j` / *** | 图谱认证 |

### 安全与 Gateway

| 变量 | 说明 |
|------|------|
| `JWT_SECRET` 或 `JWT_PRIVATE_KEY_PATH` | HS256 密钥或 RS256 私钥路径 |
| `JWT_PUBLIC_KEY_PATH` | RS256 公钥（若分离验证） |
| `JWT_TTL_SECONDS` | Access TTL，默认 `1800` |
| `REFRESH_TTL_SECONDS` | Refresh TTL，默认 `604800` |
| `CORS_ORIGINS` | 逗号分隔源列表 |
| `COOKIE_SECURE` | 生产 `true` |
| `AUTH_API_KEYS_ENABLED` | 是否启用 API Key，默认 `true` |

### 内部服务

| 变量 | 说明 |
|------|------|
| `RUNTIME_BASE_URL` | Gateway → Runtime |
| `LITELLM_BASE_URL` | `http://litellm:4000` |
| `LITELLM_MASTER_KEY` | 调用 LiteLLM 的主密钥 |
| `LITELLM_DEFAULT_MODEL` | 默认逻辑模型名（映射到路由） |
| `PUBLIC_API_BASE` / `PUBLIC_WS_BASE` | 前端构建期公开基址 |
| `LOG_LEVEL` | `INFO` / `DEBUG` |
| `ENV` | `dev` / `staging` / `prod` |

### 可选组件

| 变量 | 组件 |
|------|------|
| `OPENSEARCH_URL` | OpenSearch |
| `GOTENBERG_URL` | `http://gotenberg:3000` |
| `N8N_WEBHOOK_URL` | 通知回调基址 |
| `OLLAMA_BASE_URL` | `http://ollama:11434` |
| `ENABLE_OPENSEARCH` | `true/false` |
| `ENABLE_PDF_EXPORT` | `true/false` |
| `ENABLE_N8N_HOOKS` | `true/false` |

### 云模型密钥（经 LiteLLM，按需）

`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`GEMINI_API_KEY`、`DEEPSEEK_API_KEY`、`DASHSCOPE_API_KEY`（Qwen）等。未配置的供应商不得出现在默认路由中。

## `.env.example` 骨架

```bash
# deploy/env/.env.example
ENV=dev
POSTGRES_PASSWORD=change_me_pg
NEO4J_PASSWORD=change_me_neo4j
MINIO_ROOT_USER=rosminio
MINIO_ROOT_PASSWORD=change_me_minio
MINIO_ACCESS_KEY=rosapp
MINIO_SECRET_KEY=change_me_minio_app
JWT_SECRET=change_me_use_long_random_string
LITELLM_MASTER_KEY=sk-litellm-change_me
CORS_ORIGINS=http://localhost:3000
PUBLIC_API_BASE=http://localhost:8000
PUBLIC_WS_BASE=ws://localhost:8000
LOG_LEVEL=INFO

# Optional cloud keys
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# Feature flags
ENABLE_OPENSEARCH=false
ENABLE_PDF_EXPORT=false
ENABLE_N8N_HOOKS=false
```

复制为 `.env` 并替换所有 `change_me_*`。`.env` 不得提交 Git。

## LiteLLM 配置

`deploy/configs/litellm.yaml` 概念示例：

```yaml
model_list:
  - model_name: default
    litellm_params:
      model: openai/gpt-4.1-mini
      api_key: os.environ/OPENAI_API_KEY

  - model_name: strong
    litellm_params:
      model: anthropic/claude-sonnet-4-20250514
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: local
    litellm_params:
      model: ollama/qwen2.5:14b
      api_base: http://ollama:11434

router_settings:
  routing_strategy: simple-shuffle

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
```

ResearchOS 的 `model_profile`（如研究任务 `options.model_profile`）映射到上述 `model_name`，而不是供应商原始模型 ID。这样更换供应商无需改前端。

## 应用特性开关

| Flag | 默认 | 含义 |
|------|------|------|
| `HUMAN_INTERRUPT_DEFAULT` | `on_review` | 新任务默认中断策略 |
| `CITATION_REQUIRED_DEFAULT` | `true` | 默认强制引用 |
| `MAX_TASKS_PER_HOUR` | `20` | 每用户创建上限 |
| `WS_EVENT_BUFFER_TTL_SEC` | `86400` | 事件缓冲 TTL |
| `INGEST_MAX_UPLOAD_MB` | `100` | 上传上限 |
| `GRAPH_EXTRACT_ENABLED` | `true` | 入库时抽实体 |

## 前端配置

仅允许：

```bash
NEXT_PUBLIC_API_BASE=https://research.example.com
NEXT_PUBLIC_WS_BASE=wss://research.example.com
NEXT_PUBLIC_APP_NAME=ResearchOS
```

禁止 `NEXT_PUBLIC_` 前缀下出现任何密钥。认证令牌运行时获取。

## 配置校验

`bootstrap` / Gateway 启动时应校验：

1. 必填变量存在且非占位符 `change_me`
2. `DATABASE_URL`、`REDIS_URL` 可连接（ready 检查）
3. `JWT_SECRET` 长度足够（例如 ≥ 32 字节）
4. 若 `ENABLE_PDF_EXPORT=true` 则 `GOTENBERG_URL` 可达
5. 若默认 `model_profile` 指向 `local`，则 Ollama 可达

失败时进程以非零退出，避免「半启动」吞请求。

## 密钥轮换

| 密钥 | 轮换方式 |
|------|----------|
| `JWT_SECRET` | 双密钥重叠窗口；短 TTL access 加速失效 |
| MinIO / DB 密码 | 滚动更新 Compose secret + 重载 |
| LiteLLM master | 更新后滚动 gateway/runtime |
| 用户 API Key | 用户自助吊销；管理员可强制 |

轮换操作写入审计日志。

## 多环境差异

| 项 | dev | prod-private |
|----|-----|--------------|
| TLS | 否 | 终止于反向代理 |
| CORS | localhost | 精确域名 |
| `LOG_LEVEL` | DEBUG | INFO |
| 云模型 | 常用 | 可选禁用，仅 Ollama |
| n8n | 可选 | 内网 + SSO |
| 备份 | 手动 | 自动定时 |

私有化更多约束见 [04-private-deployment.md](./04-private-deployment.md)。
