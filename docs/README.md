# ResearchOS 文档索引 / Documentation Index

> Agent-first Deep Research OS — 自主研究、知识进化与工程决策支持平台。

本文档体系是 ResearchOS 的**单一事实来源（Single Source of Truth）**。实现代码、部署配置与产品决策均应可追溯到此处。

---

## 快速导航 / Quick Links

| 读者 | 建议入口 |
|------|----------|
| 新贡献者 | [产品定义](./core/00-product-definition.md) → [架构总览](./01-Architecture.md) → [仓库布局](./03-Repository-Layout.md) |
| 架构师 / Tech Lead | [设计原则](./core/01-design-principles.md) → [ADR 索引](./adr/README.md) → [技术选型](./04-Technology-Selection.md) |
| 产品 / 业务 | [愿景](./00-Vision.md) → [竞争格局](./core/02-competitive-landscape.md) → [路线图](./05-Development-Roadmap.md) |
| 工程师落地 | [系统设计](./02-System-Design.md) → Runtime / Agents / Knowledge / MCP 专题 |

根目录还有：

- [`/README.md`](../README.md) — 项目主页
- [`/ROADMAP.md`](../ROADMAP.md) — 分阶段交付计划（与文档对齐）

---

## 1. 核心文档 / Core

| 文档 | 说明 |
|------|------|
| [00-Vision](./00-Vision.md) | 愿景、定位与长期目标 |
| [01-Architecture](./01-Architecture.md) | 分层架构、组件边界、部署视图 |
| [02-System-Design](./02-System-Design.md) | 研究流水线、状态模型、接口契约 |
| [03-Repository-Layout](./03-Repository-Layout.md) | 仓库目录约定与模块职责 |
| [04-Technology-Selection](./04-Technology-Selection.md) | 技术栈选型与替代方案 |
| [05-Development-Roadmap](./05-Development-Roadmap.md) | 开发阶段与里程碑 |

### 核心专题 `docs/core/`

| 文档 | 说明 |
|------|------|
| [00-product-definition](./core/00-product-definition.md) | 产品定义、Non-Goals、Persona |
| [01-design-principles](./core/01-design-principles.md) | Agent First / MCP Native / Knowledge Evolution 等六大原则 |
| [02-competitive-landscape](./core/02-competitive-landscape.md) | 与 Deep Research / RAG / n8n 的差异化 |
| [03-glossary](./core/03-glossary.md) | 术语表（Agent、Hybrid RAG、Checkpoint、HyDE 等） |

---

## 2. 架构决策记录 / ADR

| ADR | 标题 |
|-----|------|
| [ADR Index](./adr/README.md) | 决策索引与状态 |
| [0001](./adr/0001-agent-runtime-langgraph.md) | Agent Runtime → LangGraph |
| [0002](./adr/0002-mcp-native-tools.md) | MCP-Native 工具层 |
| [0003](./adr/0003-hybrid-graphrag.md) | Hybrid GraphRAG（Graph + Vector + Fulltext） |
| [0004](./adr/0004-model-gateway-litellm.md) | 模型网关 → LiteLLM |
| [0005](./adr/0005-n8n-orchestration-boundary.md) | n8n 边界：非核心运行时 |
| [0006](./adr/0006-report-pipeline-markdown-typst.md) | 报告管线 Markdown → Typst/Pandoc |
| [0007](./adr/0007-search-router-mcp.md) | 搜索路由器（MCP Search Router） |

---

## 3. 专题文档 / Topics

| 目录 | 说明 |
|------|------|
| [`agents/`](./agents/README.md) | Supervisor / Planner / Research / ETL / Analysis / Reviewer / Writer / Memory / Citation |
| [`runtime/`](./runtime/LangGraph-Runtime.md) | LangGraph 状态机、Checkpoint、Streaming、Human-in-the-loop |
| [`knowledge/`](./knowledge/README.md) | GraphRAG、ETL、语义分块、混合检索、HyDE、引用溯源 |
| [`mcp/`](./mcp/README.md) | MCP 架构、Search/Browser/Parser/KG/Report 工具与权限 |
| [`api/`](./api/README.md) | Gateway REST / Auth / Research API / Knowledge API / WebSocket |
| [`workflows/`](./workflows/README.md) | 竞品分析、Deep Research、持续学习工作流 |
| [`frontend/`](./frontend/README.md) | 流式 UI、引用展示、研究控制台 |
| [`deployment/`](./deployment/README.md) | Docker Compose、配置、GPU/Ollama、私有化、可观测性 |
| [`industrial/`](./industrial/README.md) | Robotics / ROS2 / PLC / CAD / Isaac Sim 扩展 |
| [`reference/`](./reference/source-conversation-summary.md) | 源对话摘要与架构决策速查 |
| [`CONTRIBUTING.md`](./CONTRIBUTING.md) | 架构阶段贡献指南 |

---

## 4. 架构演进一句话 / Architecture Evolution

**不是** 2024 年 n8n 中心的「搜索 → 下载 → Embedding → RAG → LLM → PDF」。

**而是**：

```text
Planner → Research → ETL → Knowledge Graph + Vector → Analysis Agents → Reviewer → Report
```

业务逻辑落在 **Python Agent Runtime + MCP Tools**；n8n 仅可选用于调度与通知。详见 [ADR-0005](./adr/0005-n8n-orchestration-boundary.md)。

---

## 5. 文档约定 / Conventions

1. **中英混排**：标题优先中文，关键术语保留英文（如 Hybrid RAG、Checkpoint）。
2. **ADR 不可静默变更**：改变已 Accepted 决策时，新增 ADR 或修订 Status 并说明原因。
3. **先文档后代码**：重大模块以 ADR + 设计文档驱动实现（Docs-Driven Development）。
4. **链接相对路径**：文档间交叉引用使用仓库相对路径，便于离线阅读与 PR Review。

---

## 6. 贡献文档 / Contributing Docs

1. 在对应目录新增或修订 Markdown。
2. 更新本索引与相关 ADR / ROADMAP 链接。
3. 术语变更同步更新 [术语表](./core/03-glossary.md)。
4. PR 描述中注明影响的文档路径与决策状态。
