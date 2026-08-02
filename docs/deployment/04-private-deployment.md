# 私有化部署

ResearchOS 的设计原则之一是 **Private Deployment**：企业可在自有机房或 VPC 内完整运行，数据、密钥与知识资产默认不出边界。本文给出私有化基线架构、网络隔离、身份集成与运维要求。

## 私有化目标

1. 研究问题、文档、报告、图谱均存储在客户控制的基础设施内
2. 模型推理可纯本地（Ollama/vLLM），或经审批的出站代理访问云 API
3. 管理人员可审计「谁在何时检索/导出了什么」
4. 可选气隙：无互联网仍能基于内网知识库完成研究

## 参考拓扑

```
                     ┌──────────── 企业 IdP (OIDC) ────────────┐
                     ▼                                         │
[用户浏览器] ──TLS──► [反向代理 / WAF] ──► frontend + gateway    │
                                        │                      │
                                        ▼                      │
                               ros_internal VPC                │
                    runtime workers litellm postgres            │
                    redis minio qdrant neo4j (opensearch)       │
                                        │                      │
                          ┌─────────────┴─────────────┐        │
                          ▼                           ▼        │
                   Ollama / vLLM              (可选) 出站代理    │
                   内网 GPU 池                 仅 litellm 出口   │
```

n8n 若启用：置于内网，仅运维可达；定时任务回调 Gateway 内网地址。

## 部署清单

### 基础设施

- 容器平台：Docker Compose（中小）或 Kubernetes（大规模）
- 块存储 / 对象存储持久卷；生产禁用「仅容器可写层」存数据
- TLS 证书：企业 PKI 或 ACME；WebSocket 同域或明确 `wss` 证书覆盖
- 备份存储：与生产隔离的二次位置

### 应用栈

与 [01-docker-compose.md](./01-docker-compose.md) 核心服务一致；生产额外要求：

| 项 | 要求 |
|----|------|
| 镜像 | 私有镜像仓库；固定 digest，避免 `latest` 盲升 |
| 密钥 | Vault / K8s Secret / Docker secret；禁止明文进 Git |
| 数据库 | 主从或托管 PostgreSQL；定期逻辑备份 + PITR（若可得） |
| 对象存储 | MinIO 纠删码或多盘；或对接企业 S3 兼容存储 |
| 入口 | 仅暴露 443；管理端口（Neo4j Browser、MinIO Console、n8n）走 VPN / SSO |

## 网络策略

| 流向 | 策略 |
|------|------|
| 互联网 → 集群 | 仅 HTTPS 到反向代理 |
| 浏览器 → Neo4j/Qdrant/Redis/MinIO/Postgres | **拒绝** |
| Gateway → 数据面 | 允许 |
| LiteLLM → 公网模型 API | 默认拒绝；白名单域名 + 出站代理 |
| Runtime → 任意公网 | 仅经 MCP 工具策略；可按工作空间关闭 `enable_web` |
| 运维 → 管理 UI | VPN / 堡垒机 |

域名示例：

- `https://research.internal.corp` — 用户入口
- `https://research-api.internal.corp` — 可选拆分 API
- 管理类子域不解析到公网 DNS

## 身份与访问

1. **阶段 A**：本地账号 + API Key（架构期 / 小团队）
2. **阶段 B**：OIDC 对接企业 IdP（Entra ID / Keycloak / Okta）
3. 强制 SSO 后禁用本地注册；保留 break-glass 本地管理员（离线保管）
4. 工作空间 RBAC：`member` / `editor` / `admin`
5. 工业知识空间可设更高密级标签，限制导出

会话与鉴权细节见 [../api/02-auth-and-sessions.md](../api/02-auth-and-sessions.md)。

## 数据驻留与分类

| 数据类 | 存储 | 出境 |
|--------|------|------|
| 原始文档 | MinIO | 禁止（除非合规审批） |
| 向量 / 图谱 | Qdrant / Neo4j | 禁止 |
| 任务与报告元数据 | PostgreSQL | 禁止 |
| 提示词与模型补全 | 取决于模型部署 | 本地模型：不出境；云模型：经 DLP/代理策略 |
| 遥测 | 自建观测栈 | 默认不出第三方 SaaS |

对云模型场景，建议：

- 剥离附件二进制，仅发送必要文本片段
- 开启企业与供应商的零保留（zero retention）合同能力（若有）
- 高密级工作空间强制 `model_profile=local`

## 备份与恢复

每日至少：

```bash
# 概念步骤
pg_dump → 加密对象存储
mc mirror minio 关键 → 备份桶
neo4j-admin dump
qdrant snapshot（或依赖原文可重建策略）
```

恢复演练：每季度在隔离环境执行一次全量恢复，并验证：

- 登录与会话
- 随机文档检索命中
- 历史任务报告可打开

RPO/RTO 目标由客户约定；文档建议基线 RPO ≤ 24h，RTO ≤ 8h（单机 Compose）。

## 升级

1. 读 changelog / ADR
2. 备份
3. 预发验证迁移脚本（PostgreSQL Alembic 等）
4. 滚动更新 `worker` → `runtime` → `gateway` → `frontend`
5. 观察错误率与 ready 探针
6. 失败则回滚镜像 digest + 数据库迁移回退策略（迁移须向后兼容一个版本）

## 合规与审计

Gateway 审计事件至少包括：登录成败、权限拒绝、文档上传/下载、知识空间删除、报告导出、API Key 生命周期、管理员配置变更。

审计日志：

- 写 PostgreSQL（热）
- 定期归档 MinIO（冷）
- 只追加，普通角色不可改

## 气隙检查表

- [ ] 所有镜像已导入私有仓库
- [ ] Ollama 模型已预置
- [ ] 云 API Key 为空；LiteLLM 无外网路由
- [ ] `enable_web` 默认 false
- [ ] DNS/防火墙无出站
- [ ] 许可证与字体等导出依赖已内置（Typst/Gotenberg 资源）
- [ ] 时间同步（内部 NTP）正常——JWT 依赖时钟

## 与「文档驱动」的关系

私有化现场的差异（网络、IdP、气隙）应记录在客户侧 runbook，但**通用机制**留在本仓库 `docs/deployment`。向 [github.com/Roarpeng/ResearchOS](https://github.com/Roarpeng/ResearchOS) 贡献时，只提交可公开的模式与示例，不含客户密钥与拓扑细节。
