# Docker Compose 服务与职责

本文描述 ResearchOS 在 Docker Compose 下的服务清单、职责边界，以及概念性 compose 大纲（非必须与最终文件逐字相同，但职责应对齐）。

## 服务总表

### 核心必选

| 服务名 | 镜像方向 | 端口（宿主机示例） | 职责 |
|--------|----------|-------------------|------|
| `postgres` | `postgres:16` | `5432` | 用户、会话、任务元数据、审计、知识元数据 |
| `redis` | `redis:7` | `6379` | 会话缓存、限流、事件流缓冲、短期锁 |
| `minio` | `minio/minio` | `9000` / `9001` | 文档原文、报告附件、工具产物对象存储 |
| `qdrant` | `qdrant/qdrant` | `6333` | 向量检索 |
| `neo4j` | `neo4j:5` | `7474` / `7687` | 知识图谱 |
| `litellm` | `ghcr.io/berriai/litellm` | `4000` | 多模型统一网关 |
| `gateway` | 自建 | `8000` | FastAPI：鉴权、会话、API、WS |
| `runtime` | 自建 | 内部 | LangGraph 执行、checkpoint、interrupt |
| `worker-knowledge` | 自建 | 内部 | 解析、嵌入、图谱抽取、入库作业 |
| `frontend` | 自建 / nginx | `3000` 或 `80` | 流式研究 UI |

### 可选组件

| 服务名 | 何时启用 | 职责 |
|--------|----------|------|
| `opensearch` | 需要强全文检索 / 大规模关键词 | Hybrid 中的 keyword 通道 |
| `gotenberg` | 需要 PDF 导出 | HTML/Office → PDF |
| `typst` / 报告渲染 sidecar | 需要高质量排版 PDF | Markdown/Typst → PDF |
| `n8n` | 需要定时研究触发、邮件/IM 通知 | **仅** schedule / notify，不跑 Agent 推理 |
| `ollama` | 本地/私有模型 | 见 [03-gpu-and-ollama.md](./03-gpu-and-ollama.md) |
| `openclaw` 等浏览器自动化 | 需要稳健抓取 | 经 MCP 暴露，不直连前端 |

## 职责边界（重要）

```
n8n ──cron/webhook──► Gateway API ──► Runtime (Agent)
n8n ──notify◄──────── Gateway/Runtime 事件钩子

禁止：在 n8n 内编写多步研究 Agent、RAG 主链路、模型编排核心逻辑。
```

原始「纯 n8n RAG 竞品分析工作流」被明确降级为外设；研究操作系统能力集中在 Gateway + Runtime + Knowledge。

## 网络与卷

建议网络：

- `ros_public`：frontend、gateway（对外）
- `ros_internal`：全部后端与数据面（默认不映射到宿主机，除调试）

建议命名卷：

| 卷 | 用途 |
|----|------|
| `pg_data` | PostgreSQL |
| `redis_data` | Redis AOF/RDB |
| `minio_data` | 对象 |
| `qdrant_data` | 向量 |
| `neo4j_data` / `neo4j_logs` | 图谱 |
| `opensearch_data` | 全文（可选） |
| `n8n_data` | 工作流定义（可选） |
| `ollama_models` | 本地模型（可选） |

## 概念性 Compose 大纲

以下为**概念大纲**，用于对齐服务拓扑；实现时可拆 profile（`core`、`search`、`export`、`automation`、`gpu`）。

```yaml
# deploy/docker-compose.yml（概念示例）
name: researchos

x-restart: &restart
  restart: unless-stopped

services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: researchos
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: researchos
    volumes:
      - pg_data:/var/lib/postgresql/data
    networks: [ros_internal]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U researchos"]
      interval: 10s
      timeout: 5s
      retries: 5
    <<: *restart

  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis_data:/data
    networks: [ros_internal]
    <<: *restart

  minio:
    image: minio/minio:latest
    command: ["server", "/data", "--console-address", ":9001"]
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - minio_data:/data
    networks: [ros_internal]
    <<: *restart

  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - qdrant_data:/qdrant/storage
    networks: [ros_internal]
    <<: *restart

  neo4j:
    image: neo4j:5
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
      NEO4J_PLUGINS: '["apoc"]'
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
    networks: [ros_internal]
    <<: *restart

  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    volumes:
      - ./configs/litellm.yaml:/app/config.yaml:ro
    environment:
      LITELLM_MASTER_KEY: ${LITELLM_MASTER_KEY}
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}
    command: ["--config", "/app/config.yaml", "--port", "4000"]
    networks: [ros_internal]
    <<: *restart

  gateway:
    build: ../gateway
    environment:
      DATABASE_URL: postgresql+asyncpg://researchos:${POSTGRES_PASSWORD}@postgres:5432/researchos
      REDIS_URL: redis://redis:6379/0
      RUNTIME_BASE_URL: http://runtime:8080
      LITELLM_BASE_URL: http://litellm:4000
      JWT_SECRET: ${JWT_SECRET}
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_started }
      runtime: { condition: service_started }
    ports:
      - "8000:8000"
    networks: [ros_public, ros_internal]
    <<: *restart

  runtime:
    build: ../runtime
    environment:
      DATABASE_URL: postgresql+asyncpg://researchos:${POSTGRES_PASSWORD}@postgres:5432/researchos
      REDIS_URL: redis://redis:6379/0
      LITELLM_BASE_URL: http://litellm:4000
      QDRANT_URL: http://qdrant:6333
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_PASSWORD: ${NEO4J_PASSWORD}
      MINIO_ENDPOINT: minio:9000
    depends_on: [postgres, redis, litellm, qdrant, neo4j, minio]
    networks: [ros_internal]
    <<: *restart

  worker-knowledge:
    build: ../knowledge
    command: ["python", "-m", "knowledge.worker"]
    environment:
      DATABASE_URL: postgresql+asyncpg://researchos:${POSTGRES_PASSWORD}@postgres:5432/researchos
      REDIS_URL: redis://redis:6379/0
      QDRANT_URL: http://qdrant:6333
      NEO4J_URI: bolt://neo4j:7687
      MINIO_ENDPOINT: minio:9000
      LITELLM_BASE_URL: http://litellm:4000
    depends_on: [postgres, redis, qdrant, neo4j, minio, litellm]
    networks: [ros_internal]
    <<: *restart

  frontend:
    build: ../frontend
    environment:
      NEXT_PUBLIC_API_BASE: ${PUBLIC_API_BASE:-http://localhost:8000}
      NEXT_PUBLIC_WS_BASE: ${PUBLIC_WS_BASE:-ws://localhost:8000}
    ports:
      - "3000:3000"
    depends_on: [gateway]
    networks: [ros_public]
    <<: *restart

  # ---- profiles: search ----
  opensearch:
    profiles: ["search"]
    image: opensearchproject/opensearch:2
    environment:
      discovery.type: single-node
      DISABLE_SECURITY_PLUGIN: "true"
      OPENSEARCH_JAVA_OPTS: -Xms1g -Xmx1g
    volumes:
      - opensearch_data:/usr/share/opensearch/data
    networks: [ros_internal]
    <<: *restart

  # ---- profiles: export ----
  gotenberg:
    profiles: ["export"]
    image: gotenberg/gotenberg:8
    networks: [ros_internal]
    <<: *restart

  # ---- profiles: automation ----
  n8n:
    profiles: ["automation"]
    image: n8nio/n8n:latest
    environment:
      N8N_HOST: ${N8N_HOST:-localhost}
      WEBHOOK_URL: ${N8N_WEBHOOK_URL:-http://localhost:5678/}
      GENERIC_TIMEZONE: Asia/Shanghai
    volumes:
      - n8n_data:/home/node/.n8n
    ports:
      - "5678:5678"
    networks: [ros_public, ros_internal]
    <<: *restart

  # ---- profiles: gpu ----
  ollama:
    profiles: ["gpu"]
    image: ollama/ollama:latest
    volumes:
      - ollama_models:/root/.ollama
    networks: [ros_internal]
    # deploy.resources.reservations.devices → NVIDIA（见 03-gpu-and-ollama.md）
    <<: *restart

volumes:
  pg_data:
  redis_data:
  minio_data:
  qdrant_data:
  neo4j_data:
  neo4j_logs:
  opensearch_data:
  n8n_data:
  ollama_models:

networks:
  ros_public:
  ros_internal:
```

## 常用启动组合

```bash
# 核心研发栈
docker compose up -d

# 加上全文检索与 PDF 导出
docker compose --profile search --profile export up -d

# 加上定时通知
docker compose --profile automation up -d

# 本地 GPU 模型
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu up -d
```

## 启动顺序与健康

1. 数据面：`postgres`（healthy）→ `redis` / `minio` / `qdrant` / `neo4j`
2. `litellm`
3. `runtime`、`worker-knowledge`
4. `gateway`（readiness 依赖以上）
5. `frontend`

`gateway` 的 `/api/v1/health/ready` 应作为编排与负载均衡探活标准。

## MinIO 初始化

首次启动后创建 bucket（脚本化）：

- `ros-documents` — 入库原文
- `ros-artifacts` — 工具中间产物
- `ros-reports` — 导出报告

使用临时 `mc` 容器或 `bootstrap.sh` 完成；凭证仅来自环境变量。

## 资源建议（单机 Compose）

| 组件 | 内存建议 |
|------|----------|
| postgres | 1 GB |
| redis | 256–512 MB |
| minio | 512 MB |
| qdrant | 1–2 GB |
| neo4j | 2 GB |
| litellm | 512 MB |
| gateway + runtime + worker | 2–4 GB |
| opensearch（可选） | 1–2 GB |
| ollama（可选） | 视模型，7B ≈ 8 GB+ |

开发机低于建议时，可关闭 `opensearch` / `neo4j` APOC 重负载，并用云模型代替 Ollama。

## 备份要点

- **必须备份**：PostgreSQL、MinIO、Neo4j、Qdrant（或可重建则保留原文 + 元数据重嵌）
- **可重建**：向量索引（从 MinIO + 元数据重跑）、报告 PDF（可从 Markdown 再生成）
- n8n：导出工作流 JSON 纳入配置管理

备份脚本规范见私有部署文档。
