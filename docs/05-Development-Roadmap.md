# ResearchOS 开发路线图 / Development Roadmap

> 交付视角详见根目录 [`ROADMAP.md`](../ROADMAP.md)。本文补充**工程分解、依赖与文档对齐**。

---

## Phase 0 — Architecture（当前）

**目标：** 文档与决策冻结关键边界。

- [x] 产品定义、原则、竞争格局、术语表（`docs/core/`）
- [x] ADR-0001 … 0007
- [x] 愿景 / 架构 / 系统设计 / 布局 / 选型
- [x] 文档索引与根 README / ROADMAP
- [ ] 专题文档深化（mcp/api/workflows/frontend/deployment）— 持续

**依赖：** 无。  
**对齐：** 全部 ADR；[产品定义](./core/00-product-definition.md)

---

## Phase 1 — Infrastructure

**目标：** 数据面与模型网关可本地拉起。

部署清单：

| 服务 | 用途 |
|------|------|
| PostgreSQL | 元数据 / Checkpoint |
| Redis | 缓存 |
| MinIO | 对象存储 |
| Qdrant | 向量 |
| Neo4j | 图谱 |
| OpenSearch 或 BM25 | 全文 |
| LiteLLM | 模型网关 |
| Gateway 骨架 | `/health`、配置探测 |

工程任务：

1. `deploy/compose` 与 `.env.example`
2. 网络分区与卷持久化
3. LiteLLM chat + embedding smoke test
4. （可选）`deploy/optional/n8n` 通知示例，README 标明 peripheral

**退出标准：** Compose healthy；探测调用成功。  
**对齐：** [技术选型](./04-Technology-Selection.md)、[ADR-0004](./adr/0004-model-gateway-litellm.md)、[ADR-0005](./adr/0005-n8n-orchestration-boundary.md)

---

## Phase 2 — Agent Runtime

**目标：** Supervisor + Planner MVP + 流式 + Checkpoint。

实现：

- LangGraph Runtime 与 `TaskState`
- Supervisor / Planner 节点
- MCP Client + hello tool
- Gateway：创建任务、状态、WS/SSE
- HITL 最小中断
- 基础审计日志（tool calls）

**退出标准：** 目标→计划→可恢复；事件流可达前端（或 CLI 客户端）。  
**对齐：** [ADR-0001](./adr/0001-agent-runtime-langgraph.md)、[ADR-0002](./adr/0002-mcp-native-tools.md)、[`runtime/`](./runtime/LangGraph-Runtime.md)

---

## Phase 3 — Knowledge Engine

**目标：** 文档入库与 Hybrid 检索。

实现：

- 解析路由：Docling / MarkItDown / Unstructured
- Semantic Chunk + Embedding → Qdrant
- 全文索引
- 实体关系 → Neo4j
- RRF 融合与 Citation 字段
- MCP：`documents` / `vector-store` / `knowledge-graph`

**退出标准：** 一文档三通道可召回；Context Pack 可溯源。  
**对齐：** [ADR-0003](./adr/0003-hybrid-graphrag.md)、[`knowledge/GraphRAG.md`](./knowledge/GraphRAG.md)

---

## Phase 4 — Research Agent & Reports

**目标：** 自主研究闭环与可发布报告。

实现：

- Research / Analysis / Reviewer / Writer / Memory
- Search Router MCP（Web + internal）
- 反思环与工具预算
- Markdown 规范中间态
- Typst PDF + Pandoc DOCX
- 知识回写演示

**退出标准：** 开放问题 → 带引用 PDF；二次任务体现知识复用（演示级）。  
**对齐：** [ADR-0006](./adr/0006-report-pipeline-markdown-typst.md)、[ADR-0007](./adr/0007-search-router-mcp.md)

---

## Phase 5 — Engineering Copilot / Industrial

**目标：** 工程决策与工业域扩展。

方向：

- 机器人 / PLC / ROS2 / Isaac Sim / CAD 等知识连接器（只读优先）
- 工业调研与 Decision Memo 模板
- 多项目知识隔离与权限
- 评测集与质量仪表盘

**退出标准：** 至少一个垂直场景 E2E 演示 + 扩展指南。  
**对齐：** `docs/industrial/`、[愿景](./00-Vision.md)

---

## 跨阶段工作流

```text
设计（docs/ADR）→ 契约测试 → 实现 → 观测字段 → 更新 ROADMAP Status
```

禁止：研究主路径逻辑合入 n8n；厂商 SDK 散落；无溯源入库。

---

## 里程碑对照

| Milestone | Phase | 一句话 |
|-----------|-------|--------|
| M0 Docs | 0 | 「我们要建什么」无歧义 |
| M1 Bones | 1 | 「能在本机跑起来」 |
| M2 Brainstem | 2 | 「Agent 图能跑并恢复」 |
| M3 Memory | 3 | 「知识三通道可用」 |
| M4 Cortex | 4 | 「研究会写报告」 |
| M5 Industry | 5 | 「能帮工程决策」 |

---

## 相关文档

- [`ROADMAP.md`](../ROADMAP.md)
- [文档索引](./README.md)
- [ADR 索引](./adr/README.md)
