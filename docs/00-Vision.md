# ResearchOS 愿景 / Vision

## 产品定义

**ResearchOS** 是面向自主 AI Agent 的开源 **Research Operating System（研究操作系统）**。

它不是：

- 聊天机器人（Chatbot）
- 通用工作流引擎（以 n8n/Airflow 为业务大脑）
- 浅层「上传文档 → 问答」RAG 应用

它要成为：

> 可持续运行的智能平台——能研究外部世界、理解企业知识、维护长期记忆，并生成可审计的工程决策与技术报告。

更完整的边界、Persona 与 Non-Goals 见 [产品定义](./core/00-product-definition.md)。

---

## 定位

```text
ResearchOS = Deep Research + Knowledge OS + Engineering Copilot
```

| 支柱 | 含义 |
|------|------|
| Deep Research | 多步规划、工具使用、反思、引用 |
| Knowledge OS | Hybrid GraphRAG + ETL + 知识进化 |
| Engineering Copilot | 面向选型、标准、方案与风险的决策支持 |

---

## 架构愿景：从流水线到研究闭环

### 我们拒绝的范式（2024 n8n-centric RAG）

```text
Search → Download → Embedding → RAG → LLM → PDF
```

问题：状态不可控、知识不沉淀、工具难扩展、编排错位。

### 我们坚持的范式

```text
Planner → Research → ETL → Knowledge Graph + Vector → Analysis Agents → Reviewer → Report
```

要点：

- **Agent First** — LangGraph 状态机与 Checkpoint
- **MCP Native** — 工具可替换、可审计
- **Hybrid RAG** — Graph + Vector + Fulltext
- **Model Independent** — LiteLLM
- **n8n Optional** — 仅调度/通知，见 [ADR-0005](./adr/0005-n8n-orchestration-boundary.md)

---

## 目标场景

- 工业技术调研与方案选型
- 竞品与产品路线分析
- 专利与标准解读
- 学术 / 技术文献综述
- 工程方案设计与 Decision Memo
- 企业知识智能化（内外知识融合）

---

## 设计原则（摘要）

1. **Agent First** — 可调度、可恢复的 Agent 是产品单元  
2. **MCP Native** — 外部能力一律 MCP 化  
3. **Knowledge Evolution** — 研究产物回流知识层  
4. **Model Independent** — 不绑定单一 LLM 厂商  
5. **Private Deployment** — 默认支持私有化  
6. **Docs-Driven Development** — 重大能力先文档/ADR  

展开见 [设计原则](./core/01-design-principles.md)。

---

## 长期目标

提供类似「操作系统」的开放基础：

- 进程模型 ↔ Agent Runtime  
- 系统调用 ↔ MCP Tools  
- 文件系统 / DB ↔ Knowledge Layer  
- 设备驱动 ↔ 领域连接器（工业、代码、专利…）  
- 用户态应用 ↔ Research / Copilot 工作流  

使组织可以在**自己的基础设施上**运行可控、可扩展、可审计的深度研究智能体集群。

---

## 成功时的样子

一位研究工程师提出问题后：

1. Supervisor 生成可审查计划  
2. Research Agent 经 Search Router 与浏览器收集证据  
3. ETL 将新材料写入图谱与向量库  
4. Analysis / Reviewer 检查覆盖与引用  
5. Writer 产出 Markdown，Typst 渲染 PDF  
6. 下次相关问题直接受益于已进化的知识层  

而平台团队始终保有：模型选择权、数据主权、工具扩展权。

---

## 相关文档

- [产品定义](./core/00-product-definition.md)
- [竞争格局](./core/02-competitive-landscape.md)
- [架构](./01-Architecture.md)
- [路线图](../ROADMAP.md)
