# ResearchOS 系统设计 / System Design

## 1. Overview

ResearchOS 是面向自主研究与工程智能的 **Agent Operating System**。系统设计遵循：

- Agent First
- MCP Native
- Knowledge Centric（Knowledge Evolution）
- Model Independent

本文描述**运行时行为、状态模型、研究流水线与接口契约**；分层组件见 [架构](./01-Architecture.md)。

---

## 2. System Layers（逻辑）

```text
Frontend
    │
API Gateway (FastAPI)
    │
Agent Runtime (LangGraph)
    │
Supervisor Agent
    │
┌───────────────────────────────────────┐
│ Planner │ Research │ Analysis         │
│ Reviewer │ Writer │ Memory            │
└───────────────────────────────────────┘
    │
MCP Tool Layer
    │
Knowledge Layer (Hybrid GraphRAG)
    │
Storage Layer (PG / Redis / MinIO / Neo4j / Qdrant / OpenSearch)
```

外围：LiteLLM；可选 n8n（调度/通知 only）。

---

## 3. Core Components

### 3.1 API Gateway

职责：

- 认证、会话、RBAC（随阶段演进）
- 任务生命周期 API：`create` / `get` / `cancel` / `resume`
- 流式事件：节点迁移、工具调用、token、HITL 请求
- Webhook：供可选 n8n 触发与回调

契约原则：Gateway DTO ≠ 内部 `TaskState` 全量泄露；对前端提供稳定视图模型。

### 3.2 Agent Runtime

基于 LangGraph（[ADR-0001](./adr/0001-agent-runtime-langgraph.md)）。

职责：

- 状态机执行与边条件
- Checkpoint 写入/恢复
- 工具调用编排（经 MCP Client）
- 重试、超时、Human interrupt
- 结构化事件总线 → Gateway

### 3.3 Supervisor 与专家 Agent

| 组件 | 输入 | 输出 |
|------|------|------|
| Supervisor | goal、策略配置 | 阶段控制、最终验收 |
| Planner | goal | plan（任务列表、预算、停止条件） |
| Research | plan step | evidence[]、中间 claims |
| Analysis | evidence/claims | 结构化分析结果 |
| Reviewer | draft + evidence | critique / approve / request_revision |
| Writer | approved claims + outline | Markdown artifact |
| Memory | 任务产物 | 入库指令 / 去重结果 |

规则：Supervisor 管理执行，不直接做深度研究。

### 3.4 Knowledge Engine

Hybrid 架构（[ADR-0003](./adr/0003-hybrid-graphrag.md)）：

- Qdrant 语义检索
- Neo4j 关系扩展
- OpenSearch/BM25 全文
- PostgreSQL 元数据与引用
- MinIO 原文与制品

ETL：解析（Docling / MarkItDown / Unstructured）→ Semantic Chunk → Embed + Index + Entity Extract。

### 3.5 Model Gateway

LiteLLM（[ADR-0004](./adr/0004-model-gateway-litellm.md)）：逻辑模型名路由；Chat 与 Embedding 分离配置。

---

## 4. Research Flow（主路径）

```text
Question / Goal
      │
      ▼
   Planner
      │
      ▼
 Research Tasks ──► MCP Tools (Search Router / Browser / …)
      │
      ▼
 Knowledge Retrieval / ETL Upsert
      │
      ▼
   Analysis
      │
      ▼
   Reviewer ──reject──►（回到 Research / Writer）
      │ approve
      ▼
 Report Generation (Markdown → Typst/Pandoc)
      │
      ▼
 Memory / Knowledge Evolution
```

这与被否决的线性 RAG 流水线本质不同：存在**规划、多轮工具、评审环、知识回写**。

---

## 5. State Model（最小）

```text
TaskState
├── task_id
├── goal
├── plan                 # steps, budgets, stop criteria
├── messages / scratch   # 工作记忆（可裁剪）
├── evidence[]           # 证据对象
├── claims[]             # 论断 + confidence
├── citations[]          # claim ↔ source 映射
├── critique             # Reviewer 输出
├── artifacts[]          # md/pdf/docx URIs
├── status               # pending|running|awaiting_human|done|failed
└── error / metrics
```

Checkpoint 在关键节点后持久化；HITL 从中断点 resume。

---

## 6. Tool & Citation Contracts（摘要）

### SearchHit（Search Router）

`id, title, url/source_id, snippet, score, source_type, published_at?, raw_ref`

### Evidence

`evidence_id, source_id, locator, text, retrieved_by, hash`

### Citation

`citation_id, claim_id, source_id, locator, quote?`

无 Citation 的关键 Claim：Reviewer 默认要求修订或降级为「待验证」。

---

## 7. Report Pipeline

见 [ADR-0006](./adr/0006-report-pipeline-markdown-typst.md)。

```text
Approved Claims + Outline
        → Writer → Markdown (canonical)
        → MCP report.render
        → Typst PDF / Pandoc DOCX
        → MinIO artifact URI
```

---

## 8. Design Principles（落到机制）

### Persistent Intelligence

- Memory Agent + ETL Upsert 强制路径（可配置延迟批写）
- 实体冲突合并策略文档化

### Tool Extensibility

- 新能力 = 新 MCP Server + 契约测试
- Tool Budget 由 Planner/Supervisor 强制

### Model Independence

- 禁止业务代码直锁厂商 SDK
- 评测时同一图切换逻辑模型名

### n8n Boundary

- 只调用 Gateway 任务 API
- 不复制研究状态机（[ADR-0005](./adr/0005-n8n-orchestration-boundary.md)）

---

## 9. Failure & Degradation

| 场景 | 行为 |
|------|------|
| 模型超时 | LiteLLM 重试 / fallback；节点标 failed 或降级模型 |
| 搜索配额耗尽 | 停止扩展搜索，基于已有 evidence 进入 Analysis，并标注覆盖风险 |
| 知识库不可用 | 可降级为仅 Web（若策略允许）或失败快返回 |
| 渲染失败 | 保留 Markdown；任务部分成功 + 错误码 |
| HITL 超时 | 按策略取消或自动继续（部署可配） |

---

## 10. 相关文档

- [架构](./01-Architecture.md)
- [Supervisor Agent](./agents/Supervisor-Agent.md)
- [LangGraph Runtime](./runtime/LangGraph-Runtime.md)
- [GraphRAG](./knowledge/GraphRAG.md)
- [术语表](./core/03-glossary.md)
