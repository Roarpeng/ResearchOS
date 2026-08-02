# ResearchOS 技术选型 / Technology Selection

> 决策细节以 ADR 为准；本文是选型总表与替代方案速查。

---

## 1. Runtime & API

| 组件 | 选择 | 原因 | ADR |
|------|------|------|-----|
| Agent Runtime | **LangGraph** | 有状态图、Checkpoint、HITL、Python 生态 | [0001](./adr/0001-agent-runtime-langgraph.md) |
| API Gateway | **FastAPI** | Async、类型、OpenAPI、与 Python Agent 同栈 | — |
| 外围自动化 | **n8n（可选）** | 仅调度/通知；非核心 Runtime | [0005](./adr/0005-n8n-orchestration-boundary.md) |

**未选：** 以 n8n/Airflow/Temporal 作为 AI 研究主 Runtime；纯自研状态机（短期）。

---

## 2. Model Layer

| 组件 | 选择 | 原因 | ADR |
|------|------|------|-----|
| Model Gateway | **LiteLLM** | 多 Provider、fallback、统一配置 | [0004](./adr/0004-model-gateway-litellm.md) |

**支持目标（非锁定）：** OpenAI、Claude、Gemini、Qwen、DeepSeek、Ollama 等。

**原则：** 基础设施与模型供应商解耦；Chat 与 Embedding 路由分离。

---

## 3. Tools

| 组件 | 选择 | 原因 | ADR |
|------|------|------|-----|
| Tool Protocol | **MCP** | 开放、可替换、可审计 | [0002](./adr/0002-mcp-native-tools.md) |
| Search 入口 | **Search Router MCP** | 多源归一、权限与预算 | [0007](./adr/0007-search-router-mcp.md) |

**未选：** Agent 内直嵌各搜索 SDK；以 n8n 节点当工具总线。

---

## 4. Knowledge & Storage

| 组件 | 选择 | 目的 | ADR |
|------|------|------|-----|
| Graph DB | **Neo4j** | 实体关系 / GraphRAG | [0003](./adr/0003-hybrid-graphrag.md) |
| Vector DB | **Qdrant** | 语义检索 | [0003](./adr/0003-hybrid-graphrag.md) |
| Fulltext | **OpenSearch 或 BM25 引擎** | 词法精确召回 | [0003](./adr/0003-hybrid-graphrag.md) |
| Metadata | **PostgreSQL** | 业务数据、Checkpoint、引用索引 | — |
| Object Storage | **MinIO** | 文档与报告制品（S3 兼容） | — |
| Cache | **Redis** | 热数据、限流辅助 | — |

**混合检索默认：** Graph + Vector + Fulltext，融合 RRF。

**可替换性：** 全文引擎与向量库允许适配器替换，但生产叙事保持三通道。

---

## 5. Document ETL

| 组件 | 选择 | 说明 |
|------|------|------|
| 解析 | **Docling** / **MarkItDown** / **Unstructured** | 多后端适配；按文件类型路由 |
| 分块 | Semantic Chunk | 保留结构元数据与父子块 |
| 抽取 | LLM + 规则混合 | 实体/关系写入 Neo4j |

---

## 6. Report Pipeline

| 组件 | 选择 | 原因 | ADR |
|------|------|------|-----|
| 中间态 | **Markdown** | 可 Diff、可评审 | [0006](./adr/0006-report-pipeline-markdown-typst.md) |
| PDF | **Typst** | 现代、模板可控、私有化友好 | [0006](./adr/0006-report-pipeline-markdown-typst.md) |
| Office | **Pandoc** | DOCX 等兼容 | [0006](./adr/0006-report-pipeline-markdown-typst.md) |

**未选：** LLM 直接生成 PDF 二进制作为主路径。

---

## 7. Frontend（方向）

| 关注点 | 方向 |
|--------|------|
| 流式体验 | WebSocket / SSE |
| 核心视图 | 计划、证据、引用、HITL、报告 |
| 实现框架 | Phase 2+ 再锁定（保持可替换）；优先现代 React/Vue 之一 |

前端不得成为业务编排中心。

---

## 8. Deployment

| 项目 | 选择 |
|------|------|
| 默认交付 | Docker Compose |
| 演进 | Kubernetes |
| 密钥 | Env / Secret Manager |
| 观测 | 结构化日志（task_id 贯穿）；指标/追踪随阶段加强 |

---

## 9. 设计原则再声明

> Infrastructure must remain independent from model providers.  
> Business logic must remain independent from n8n.  
> Tools must remain independent from a single Agent framework SDK.

对齐：[设计原则](./core/01-design-principles.md)。

---

## 10. 相关文档

- [架构](./01-Architecture.md)
- [ADR 索引](./adr/README.md)
- [路线图](../ROADMAP.md)
