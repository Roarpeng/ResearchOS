# 产品定义 / Product Definition

## 一句话定义 / One-Liner

**ResearchOS** 是面向 AI Agent 的开源 **Deep Research Operating System**：以 Agent Runtime 为核心，通过 MCP 工具生态、Hybrid GraphRAG 知识层与多模型网关，完成自主研究、知识进化与工程决策支持。

它不是聊天机器人，不是通用工作流引擎，也不是「上传 PDF 再问答」的浅层 RAG 应用。

---

## 产品定位 / Positioning

```text
ResearchOS = Deep Research + Knowledge OS + Engineering Copilot
```

| 维度 | 说明 |
|------|------|
| Deep Research | 多步规划、工具调用、证据收集、反思与引用溯源 |
| Knowledge OS | 文档 ETL、图谱 + 向量 + 全文的长期知识演进 |
| Engineering Copilot | 面向工程/工业场景的方案对比、标准解读与决策报告 |

---

## 要解决的问题 / Problem Statement

企业与研究团队常见痛点：

1. **信息碎片化**：公开 Web、内部文档、专利、标准、代码库割裂，难以统一检索与推理。
2. **RAG 浅层化**：单纯「切块 + Embedding」无法回答关系型、对比型、演进型问题。
3. **流程不可审计**：黑盒 Deep Research 产品难私有化、难控模型、难追溯引用。
4. **知识不沉淀**：一次研究结束后上下文丢失，无法形成可复用的组织记忆。
5. **编排错位**：用 n8n 等可视化工作流承载复杂 Agent 状态机，导致可维护性崩溃。

ResearchOS 以 **Planner → Research → ETL → Knowledge → Analysis → Reviewer → Report** 闭环替代线性 RAG Pipeline。

---

## 核心能力 / Core Capabilities

| 能力 | 描述 |
|------|------|
| 自主研究环 | Supervisor 调度 Planner / Research / Reviewer / Writer / Memory |
| MCP-Native 工具 | 搜索、浏览器、文档、图谱、仓库、报告等统一为 MCP Tools |
| Hybrid RAG | Neo4j Graph + Qdrant Vector + BM25/OpenSearch Fulltext |
| 知识进化 | 研究产物回写入知识库，实体关系持续更新 |
| 模型无关 | LiteLLM 统一接入 OpenAI / Claude / Gemini / Qwen / DeepSeek / Ollama |
| 可审计报告 | Markdown 中间态 → Typst / Pandoc → PDF/DOCX，带 Citation |
| 私有部署 | Docker Compose / K8s，数据不出域 |
| 可选外围编排 | n8n 仅做定时、通知、Webhook，不承载业务状态机 |

---

## 目标场景 / Target Scenarios

- 工业技术调研与方案选型（机器人、自动化、视觉、运动控制等）
- 竞品分析与产品路线对比
- 专利与标准解读
- 学术 / 技术文献综述
- 工程方案设计与技术决策备忘录（Decision Memo）
- 企业知识智能化（内部文档 + 外部情报融合）

---

## 目标用户 / Personas

### P1 — Research Engineer（研究工程师）

- **目标**：快速完成技术调研并产出可引用报告
- **痛点**：手工搜索耗时、引用难整理、结论难复现
- **成功标准**：一次任务得到带证据链的结构化报告

### P2 — Knowledge Architect（知识架构师）

- **目标**：建设组织级知识图谱与检索体系
- **痛点**：ETL 碎片化、实体不一致、图谱与向量不同步
- **成功标准**：文档入库后可同时做语义检索与关系推理

### P3 — Engineering Lead（工程负责人）

- **目标**：基于证据做技术选型与风险判断
- **痛点**：材料散落、对比维度不全、决策过程无记录
- **成功标准**：获得可分享的 Decision Report，含置信度与待验证项

### P4 — Platform / Infra Engineer（平台工程师）

- **目标**：私有化部署、模型切换、权限与可观测
- **痛点**：供应商锁定、密钥散落、Agent 运行难调试
- **成功标准**：Compose 一键拉起；模型与工具可配置热切换

### P5 — Open Source Contributor（开源贡献者）

- **目标**：扩展 Agent、MCP Server、检索策略
- **痛点**：边界不清、缺 ADR、目录约定模糊
- **成功标准**：文档驱动贡献路径清晰，PR 可对照 ADR 评审

---

## 明确不做 / Non-Goals

下列事项**明确不在** ResearchOS 核心范围内（至少 Phase 0–4）：

| Non-Goal | 原因 |
|----------|------|
| 成为通用 ChatGPT 克隆 | 产品聚焦深度研究与知识进化，而非闲聊 |
| 用 n8n 承载核心 Agent 业务逻辑 | 状态机、Checkpoint、反思环属于 Runtime，见 ADR-0005 |
| 绑定单一 LLM 厂商 | 模型通过 LiteLLM 抽象，避免供应商锁定 |
| 只做「上传文档 → 问答」的轻量 RAG SaaS | 必须支持多源研究、图谱与长期记忆 |
| 替代专业 CAD / PLC / IDE | 工业扩展是 Copilot，不是工程工具本体 |
| 承诺「零幻觉」 | 通过 Reviewer、Citation、置信度降低风险，不宣称消除幻觉 |
| Phase 0 即完整多租户商业 SaaS | 先做好单组织私有部署与清晰权限模型 |

---

## 成功度量 / Success Metrics（方向性）

| 指标 | 说明 |
|------|------|
| Task Completion Rate | 研究任务到达「可交付报告」的比例 |
| Citation Coverage | 关键论断可回溯到 Evidence / Source 的比例 |
| Knowledge Reuse | 后续任务命中既有图谱/向量记忆的比例 |
| Human Interrupt Rate | 需人工介入的频率（过高说明 Planner 不稳定） |
| Time-to-Report | 从提问到初稿报告的中位时间 |
| Deploy Friction | 新环境 Compose 拉起成功率与耗时 |

---

## 产品边界示意 / Boundary Sketch

```text
┌─────────────────────────────────────────────────────────┐
│                     ResearchOS Core                      │
│  Gateway · LangGraph Runtime · Agents · MCP · Knowledge │
└───────────────────────────┬─────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   LLM Providers      External Tools      Optional n8n
   (via LiteLLM)      (via MCP)           (cron / notify)
```

---

## 相关文档

- [设计原则](./01-design-principles.md)
- [竞争格局](./02-competitive-landscape.md)
- [愿景](../00-Vision.md)
- [ADR 索引](../adr/README.md)
