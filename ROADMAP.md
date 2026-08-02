# ResearchOS Roadmap

> 与 [`docs/05-Development-Roadmap.md`](./docs/05-Development-Roadmap.md) 对齐；本文是面向贡献者与用户的**交付视角**路线图。  
> 架构约束见 [ADRs](./docs/adr/README.md)。

---

## 总览

```text
Phase 0  Architecture & Docs
Phase 1  Infrastructure
Phase 2  Agent Runtime
Phase 3  Knowledge Engine
Phase 4  Research Agent & Reports
Phase 5  Engineering / Industrial Intelligence
```

**主轴流水线（全阶段对齐）：**

```text
Planner → Research → ETL → Knowledge Graph + Vector → Analysis Agents → Reviewer → Report
```

---

## Phase 0 — Architecture & Docs（当前）

**目标：** 建立单一事实来源，冻结关键边界。

| 交付物 | 状态 |
|--------|------|
| 产品定义 / 原则 / 术语 / 竞争格局 | Done（`docs/core/`） |
| ADR-0001 … 0007 | Done（`docs/adr/`） |
| 愿景 / 架构 / 系统设计 / 布局 / 选型 | Done（`docs/00`–`04`） |
| 文档索引与根 README | Done |
| 目标仓库目录骨架约定 | Done（文档级） |

**退出标准：**

- 新人阅读 `docs/README.md` 后能说清「为何不是 n8n RAG」
- 所有 Accepted ADR 互相无矛盾

---

## Phase 1 — Infrastructure

**目标：** Compose 一键拉起数据面与网关依赖。

| 组件 | 用途 |
|------|------|
| PostgreSQL | 元数据、任务、Checkpoint |
| Redis | 缓存 / 辅助队列 |
| MinIO | 对象存储 |
| Qdrant | 向量 |
| Neo4j | 知识图谱 |
| OpenSearch 或 BM25 组件 | 全文 |
| LiteLLM | 模型网关 |
| FastAPI Gateway（骨架） | 健康检查、配置探测 |

**交付物：**

- `deploy/docker-compose.yml`（或等价）
- 环境变量模板与密钥约定
- 基础观测（日志字段：service、task_id）
- 可选：n8n 容器 **仅** 作通知示例（标注 peripheral）

**退出标准：**

- 干净机器 Compose up 后核心依赖 healthy
- LiteLLM 能完成一次 chat + embedding 探测调用

**对齐文档：** [技术选型](./docs/04-Technology-Selection.md)、[ADR-0004](./docs/adr/0004-model-gateway-litellm.md)、[ADR-0005](./docs/adr/0005-n8n-orchestration-boundary.md)

---

## Phase 2 — Agent Runtime

**目标：** LangGraph Runtime + Supervisor 最小闭环。

| 能力 | 说明 |
|------|------|
| TaskState | goal / plan / evidence / citations / result |
| Checkpoint | PostgreSQL checkpointer |
| Supervisor | 调度 Planner（最小）与 echo/tool demo |
| Streaming | Gateway WebSocket/SSE 事件 |
| HITL | 至少一个可中断节点 |
| MCP Client | 调用 1–2 个示例 MCP Server |

**交付物：**

- `runtime/` + `agents/supervisor` + `agents/planner`（MVP）
- 任务创建 / 状态查询 API
- 开发用 MCP hello-tool

**退出标准：**

- 用户提交目标 → 产生计划 → 可从 Checkpoint 恢复
- 工具调用出现在审计日志

**对齐文档：** [ADR-0001](./docs/adr/0001-agent-runtime-langgraph.md)、[ADR-0002](./docs/adr/0002-mcp-native-tools.md)、[`runtime/LangGraph-Runtime.md`](./docs/runtime/LangGraph-Runtime.md)

---

## Phase 3 — Knowledge Engine

**目标：** ETL + Hybrid 检索可用。

| 能力 | 说明 |
|------|------|
| 解析适配 | Docling / MarkItDown / Unstructured 至少打通主路径 |
| Semantic Chunk | 结构化分块 + 元数据 |
| Embedding 入库 | Qdrant |
| 全文索引 | BM25/OpenSearch |
| 实体关系抽取 | 写入 Neo4j（可先规则+LLM 混合） |
| Hybrid 融合 | RRF 默认 |
| Citation 溯源字段 | source_id + locator |

**交付物：**

- `knowledge/` 管道 CLI 或 Worker
- MCP：`vector-store` / `knowledge-graph` / `documents`
- 检索评测小集（内部）

**退出标准：**

- 上传文档后三通道均可召回
- Context Pack 带可验证 Citation

**对齐文档：** [ADR-0003](./docs/adr/0003-hybrid-graphrag.md)、[`knowledge/GraphRAG.md`](./docs/knowledge/GraphRAG.md)

---

## Phase 4 — Research Agent & Reports

**目标：** 端到端深度研究 + 可发布报告。

| 能力 | 说明 |
|------|------|
| Research Agent | 搜索、阅读、证据抽取 |
| Search Router MCP | 多源路由（Web + internal） |
| Analysis Agents | 对比 / 风险 / 决策维度 |
| Reviewer | 覆盖度、矛盾、引用检查 |
| Writer | Markdown 规范中间态 |
| Report MCP | Typst PDF + Pandoc DOCX |
| Memory | 研究成果回流知识层 |

**退出标准：**

- 开放问题 → 带引用 Markdown → PDF
- Reviewer 能阻断无引用关键论断（策略可配置）
- 二次相关任务能命中既有知识（演示级即可）

**对齐文档：** [ADR-0006](./docs/adr/0006-report-pipeline-markdown-typst.md)、[ADR-0007](./docs/adr/0007-search-router-mcp.md)、[产品定义](./docs/core/00-product-definition.md)

---

## Phase 5 — Engineering / Industrial Intelligence

**目标：** 工程副驾驶与工业知识域扩展。

| 方向 | 示例 |
|------|------|
| 工业技术调研模板 | 机器人、视觉、运动控制选型报告 |
| 领域连接器 | ROS2、PLC 文档源、CAD/BOM 元数据（只读优先） |
| 仿真/实验知识 | Isaac Sim 等资料入库与对比 |
| 决策备忘录 | Decision Memo 模板与评审清单 |
| 权限与多项目空间 | 团队知识隔离 |

**退出标准：**

- 至少一个工业垂直场景的端到端演示
- 领域 MCP Server 扩展指南稳定

**对齐文档：** `docs/industrial/`（待充实）、[愿景](./docs/00-Vision.md)

---

## 跨阶段工程品质（持续）

| 主题 | 要求 |
|------|------|
| Docs-Driven | 新子系统先 ADR/设计再合入主路径 |
| Observability | task_id 贯穿 Gateway → Runtime → MCP → Knowledge |
| Evaluation | 检索与研究质量回归集随 Phase 3–4 建立 |
| Security | 密钥不进 Prompt；工具 ACL；出站可控 |
| OSS DX | Compose、示例任务、贡献文档 |

---

## 明确不做（Roadmap 级）

- 用 n8n 替换 LangGraph 作为研究 Runtime
- 绑定单一 LLM 厂商
- Phase 0–2 承诺完整多租户商业 SaaS
- 「零幻觉」市场承诺

详见 [Non-Goals](./docs/core/00-product-definition.md#明确不做--non-goals)。

---

## 变更策略

路线图变更应：

1. 更新本文与 `docs/05-Development-Roadmap.md`
2. 若触及架构边界，新增或修订 ADR
3. 在根 `README.md` Status 表同步阶段状态
