# ResearchOS 开发路线图 / Development Roadmap

> 交付视角详见根目录 [`ROADMAP.md`](../ROADMAP.md)。本文补充**工程分解、依赖与文档对齐**。

---

## Phase 0 — Architecture（Done）

**目标：** 文档与决策冻结关键边界。

- [x] 产品定义、原则、竞争格局、术语表（`docs/core/`）
- [x] ADR-0001 … 0007
- [x] 愿景 / 架构 / 系统设计 / 布局 / 选型
- [x] 文档索引与根 README / ROADMAP
- [ ] 专题文档深化（mcp/api/workflows/frontend/deployment）— 持续

**依赖：** 无。  
**对齐：** 全部 ADR；[产品定义](./core/00-product-definition.md)

---

## Phase 1 — Infrastructure（MVP Done）

**目标：** 数据面与模型网关可本地拉起。

- [x] `deploy/compose` 与 `.env.example`
- [x] 网络分区与卷持久化（compose 已声明）
- [x] LiteLLM 配置骨架 + smoke 脚本
- [x] （可选）`deploy/optional/n8n` 通知示例，README 标明 peripheral
- [x] Gateway `/api/v1/health` 等骨架

**退出标准：** Compose healthy；探测调用成功（需本机 `docker compose up` 验证）。  
**对齐：** [技术选型](./04-Technology-Selection.md)、[ADR-0004](./adr/0004-model-gateway-litellm.md)、[ADR-0005](./adr/0005-n8n-orchestration-boundary.md)

---

## Phase 2 — Agent Runtime（MVP Done）

**目标：** Supervisor + Planner MVP + 流式 + Checkpoint。

- [x] LangGraph Runtime 与 `TaskState`
- [x] Supervisor / Planner 节点
- [x] MCP Client + hello tool
- [x] Gateway：创建任务、状态、WS（Runtime HTTP `/runs`）
- [x] HITL 最小中断
- [x] 基础审计日志（tool_traces）

**退出标准：** 目标→计划→可恢复；事件写入 `state.events`。  
**对齐：** [ADR-0001](./adr/0001-agent-runtime-langgraph.md)、[ADR-0002](./adr/0002-mcp-native-tools.md)、[`runtime/`](./runtime/LangGraph-Runtime.md)

---

## Phase 3 — Knowledge Engine（MVP Done → 增强）

**目标：** 文档入库与 Hybrid 检索。

- [x] 解析路由（MarkItDown 可选；Docling/Unstructured stub+fallback）
- [x] Semantic Chunk + Embedding（LiteLLM 或伪向量）
- [x] 全文 BM25（进程内）
- [x] 实体关系 → 图适配器（Neo4j 或内存）
- [x] RRF 融合与 Citation 字段
- [x] MCP：`documents` / `vector-store` / `knowledge-graph`
- [x] 查询理解 + HyDE 钩子（`HYDE_ENABLED`，LLM 可选、模板兜底）
- [x] 统一元数据过滤器 + Review 时间窗
- [x] 分型 Neo4j Schema（类型 Label / 唯一约束 / REFERENCES→Chunk / UPDATED_BY）
- [x] Embedding 策略（docs/knowledge/08：优先级/一 collection 一模型/模型戳记/跨模型拒绝/reembed CLI）

**退出标准：** 一文档三通道可召回（内存后端默认）；Context Pack 可溯源。  
**对齐：** [ADR-0003](./adr/0003-hybrid-graphrag.md)、[`knowledge/GraphRAG.md`](./knowledge/GraphRAG.md)

---

## Phase 4 — Research Agent & Reports（MVP Done → 增强）

**目标：** 自主研究闭环与可发布报告。

- [x] Research / Analysis / Citation / Reviewer / Writer / Memory
- [x] **ETL Agent**（docs/agents/03：Ingest→Parse→Index，回执 `meta.etl_receipts`，幂等）
- [x] Search Router MCP（mock + Tavily/SearXNG/**Brave**，freshness/domain/safesearch 透传）
- [x] 工具预算字段与 Reviewer 引用门禁
- [x] Markdown 规范中间态
- [x] Report MCP（Typst/Pandoc 可选降级写 md）+ `report.preview` / `report.validate_citations`
- [x] Memory 回写 + **Reviewer 矛盾检测 / success_criteria 门禁 / gap 定向回派**
- [x] Citation trust_level / publisher / accessed_at
- [x] 工作流：deep_research 多轮定向研究、continuous_learning 轻量管道、competitive_analysis 映射
- [x] MCP 安全层基座（scope 目录/角色画像/SSRF 防护/配额/审计/脱敏，`tools/security.py`）
- [x] MCP：knowledge 门面（`knowledge.retrieve`/`fulltext.search`/`ingest_status`）、`vector.delete`

**退出标准：** 开放问题 → 带引用 Markdown（PDF 视本机 Typst）；Reviewer 能阻断无引用关键论断并给出定向补充指令。  
**对齐：** [ADR-0006](./adr/0006-report-pipeline-markdown-typst.md)、[ADR-0007](./adr/0007-search-router-mcp.md)

---

## Phase 5 — Engineering Copilot / Industrial（MVP）

**目标：** 工程决策与工业域扩展。

- [x] ROS2 / PLC / CAD 只读连接器（PLC 全链路、ROS2 工作区扫描；CAD 仍 stub）
- [x] Decision Memo 模板
- [x] 扩展指南（`industrial/README.md`）
- [x] TIA 垂直场景端到端（导出→理解→分析→HITL 写回→归档）
- [x] 设备层知识图谱 + Motion/Failure 只读 Agent
- [x] mcp-plc 只读分析工具 + 手册知识化检索
- [ ] 多项目知识隔离与评测仪表盘（后续）

**退出标准：** 连接器扩展指南可用；PLC 垂直 E2E 已打通；数字孪生（Isaac Sim）待后续迭代。  
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
