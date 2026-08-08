# ResearchOS 部署文档

ResearchOS 采用 **容器优先** 部署：开发与中小规模生产以 Docker Compose 为主；大规模可演进到 Kubernetes，但架构阶段以 Compose 为规范基线。

## 文档索引

| 文档 | 内容 |
|------|------|
| [01-docker-compose.md](./01-docker-compose.md) | 服务清单、职责与 Compose 概念大纲 |
| [02-configuration.md](./02-configuration.md) | 环境变量、密钥与配置分层 |
| [03-gpu-and-ollama.md](./03-gpu-and-ollama.md) | GPU、本地模型与 Ollama 可选集成 |
| [04-private-deployment.md](./04-private-deployment.md) | 私有化、网络隔离与合规要点 |
| [05-observability.md](./05-observability.md) | 日志、指标、追踪与告警 |
| [06-plc-feature.md](./06-plc-feature.md) | PLC Intelligence 子功能：混合部署与 Openness 侧车 |

## 部署目标

1. **一键可起**：`docker compose up` 拉起核心依赖与应用骨架
2. **模型可换**：云 API 与本地 Ollama 均可，经 LiteLLM 统一
3. **数据可私有**：默认可完全内网运行，无强制 SaaS
4. **职责清晰**：n8n 仅调度/通知；研究推理在 Runtime

## 环境画像

| 画像 | 用途 | 典型组成 |
|------|------|----------|
| `dev` | 本地开发 | Compose 全套轻量配置，热重载 |
| `staging` | 预发 | 接近生产资源，外部 IdP 可选 |
| `prod-private` | 私有生产 | TLS、备份、观测、无公网依赖 |
| `prod-hybrid` | 混合 | 内网数据 + 出站调用云模型（经代理） |

## 目录约定（目标仓库）

```
deploy/
├── docker-compose.yml
├── docker-compose.override.yml    # 本地覆盖（不入库或示例）
├── docker-compose.gpu.yml         # GPU / Ollama profile
├── env/
│   ├── .env.example
│   └── .env.private.example
├── configs/
│   ├── litellm.yaml
│   ├── neo4j/
│   └── vector/
└── scripts/
    ├── bootstrap.sh
    └── backup.sh
```

## 快速心智模型

```
[Frontend] → [Gateway] → [Runtime/Agents]
                 ↓
     PostgreSQL Redis MinIO Qdrant Neo4j
                 ↓
              LiteLLM → Cloud APIs / Ollama
                 ↓
     Optional: OpenSearch, Gotenberg/Typst, n8n
```

## 前置要求

- Docker Engine 24+ 与 Docker Compose V2
- 建议 8+ CPU、16+ GB RAM（启用 Neo4j + 向量 + 本地模型时更高）
- 可选：NVIDIA Container Toolkit（GPU / Isaac 仿真相关工作负载）
- 磁盘：SSD，预留对象存储与向量索引空间

## 相关文档

- 架构总览：[../01-Architecture.md](../01-Architecture.md)
- 技术选型：[../04-Technology-Selection.md](../04-Technology-Selection.md)
- 开发路线：[../05-Development-Roadmap.md](../05-Development-Roadmap.md)
