# 竞争格局 / Competitive Landscape

本文比较 ResearchOS 与主流「深度研究」产品及常见 RAG / 自动化方案，明确**差异化**与**可替代边界**。

---

## 比较框架

对每个对照对象评估：

| 维度 | 含义 |
|------|------|
| 自主研究深度 | 多步规划、工具使用、反思与重规划能力 |
| 知识沉淀 | 是否形成可复用的组织级图谱/向量记忆 |
| 可私有化 | 是否可完整自托管、数据不出域 |
| 可扩展工具 | 工具生态是否开放（尤其 MCP） |
| 模型选择 | 是否锁定单一厂商模型 |
| 工程决策支持 | 是否面向可审计报告与决策备忘录 |
| 编排可控性 | 状态、Checkpoint、审计是否一等公民 |

---

## 对照矩阵（概览）

| 方案 | 研究深度 | 知识沉淀 | 私有化 | 工具扩展 | 模型自由 | 编排可控 |
|------|----------|----------|--------|----------|----------|----------|
| OpenAI Deep Research | 高 | 低（会话向） | 低 | 中（封闭） | 低 | 低（黑盒） |
| Gemini Deep Research | 高 | 低–中 | 低 | 中（封闭） | 低 | 低 |
| Claude Research / 计算机使用向 | 高 | 低 | 低–中 | 中 | 低 | 低–中 |
| 普通 RAG 应用 | 低 | 中（向量库） | 高 | 视实现 | 高 | 中 |
| n8n + RAG 流水线 | 低–中 | 低–中 | 高 | 中（节点） | 高 | 中（DAG） |
| **ResearchOS** | **高（目标）** | **高（目标）** | **高** | **高（MCP）** | **高（LiteLLM）** | **高（LangGraph）** |

> 注：竞品能力随产品迭代变化；上表强调**架构定位差异**，非实时功能打分。

---

## 1. vs OpenAI Deep Research

### 对方优势

- 产品质量与模型能力强，开箱即用。
- 研究轨迹对终端用户友好。
- 与 ChatGPT 生态深度集成。

### ResearchOS 差异化

| 点 | 说明 |
|----|------|
| 可私有化 OS | 完整自托管；适合合规与内网知识 |
| 知识进化 | 研究产物写入 Neo4j + Qdrant + 全文索引，跨任务复用 |
| MCP 开放工具 | 可接内部搜索、PLM、代码库、工控文档源 |
| 可审计 Runtime | Checkpoint、证据链、Human-in-the-loop 可观测 |
| 模型路由 | 可用 Claude / Qwen / 本地模型执行同一研究图 |

### 不竞争点

- 不做「消费级聊天入口」的流量产品替代。
- 短期不追求与闭源模型同等的单次研究「聪明程度」，而追求**可控、可沉淀、可扩展**。

---

## 2. vs Gemini Deep Research

### 对方优势

- 长上下文与多模态检索能力强。
- 与 Google 搜索 / Workspace 生态协同。

### ResearchOS 差异化

- **混合检索主权**：自建 Graph + Vector + Fulltext，不绑 Google 索引。
- **工程报告管线**：Markdown → Typst/Pandoc，面向技术决策文档而非仅聊天摘要。
- **Agent 图可编程**：研究策略、评审策略可由部署方定制。
- **工业扩展路径**：机器人、PLC、ROS2 等知识域可插拔（Phase 5）。

---

## 3. vs Claude Research / Agent 产品向

### 对方优势

- 强推理与长文档理解；Artifacts / 项目空间体验好。
- 工具使用与编码能力出色。

### ResearchOS 差异化

- **多 Agent 分工显式化**：Planner / Research / Reviewer / Writer / Memory，而非单一助手人格。
- **组织知识层一等公民**：图谱关系推理 + 语义检索 + BM25。
- **运行时与模型解耦**：同一套图可换模型；Claude 可以是后端之一，而非唯一。
- **OSS 可 fork**：协议、工具、检索融合策略完全可见。

---

## 4. vs 普通 RAG（Naive / Advanced RAG）

### 典型形态

```text
文档 → Chunk → Embedding → Vector Search → LLM 回答
```

即使加入重排、HyDE、父子块等技巧，主轴仍是**检索增强生成**，不是**自主研究 OS**。

### 差距

| RAG 常见上限 | ResearchOS 回应 |
|--------------|-----------------|
| 难做多跳关系问题 | GraphRAG / 实体路径推理 |
| 难做开放 Web 调研 | Research Agent + Search Router MCP |
| 无反思与评审 | Reviewer Agent + 置信度 / 待验证列表 |
| 无长期进化 | ETL 回写与 Memory Agent |
| 报告弱 | 专用 Writer + Typst/Pandoc 管线 |

ResearchOS **包含** RAG，但 RAG 只是 Knowledge Layer 的检索手段之一，不是产品定义本身。

---

## 5. vs n8n 中心的 RAG 流水线（2024 常见范式）

### 典型形态

```text
Search → Download → Embedding → RAG → LLM → PDF
```

用 n8n（或同类 iPaaS）把节点串成「研究」。

### 为何不够

1. **状态机表达力不足**：动态重规划、循环反思、并行 Agent、人机中断难以一等公民化。
2. **Checkpoint / 审计弱**：长任务恢复、证据级回放困难。
3. **工具契约不稳定**：节点与凭证绑定 UI，难形成 MCP 生态。
4. **业务逻辑可视化债务**：复杂研究策略最终变成不可测的巨型流。

### ResearchOS 边界（重要）

- **核心 Runtime = LangGraph + Python Agents + MCP**
- **n8n = 可选**：Cron 触发研究任务、失败告警、推送通知、对接企业 IM/Webhook

详见 [ADR-0005](../adr/0005-n8n-orchestration-boundary.md)。

---

## 6. 定位总结

```text
                    知识沉淀 / 私有化
                         ▲
                         │
         ResearchOS ●    │
                         │
     Self-host RAG ○     │     ○ n8n RAG
                         │
    ─────────────────────┼──────────────────► 自主研究深度
                         │
                         │         ● 闭源 Deep Research
                         │
```

ResearchOS 瞄准右上象限：**既要深度自主研究，又要可私有化与知识进化**。

---

## 7. 竞争策略（产品叙事）

1. **对科研/企业团队**：强调证据链、私有知识库、可审计报告。
2. **对平台团队**：强调 MCP、LiteLLM、Compose 私有部署。
3. **对自动化团队**：明确 n8n 的「能做什么 / 不能做什么」，避免架构误用。
4. **对开源社区**：用 ADR 与清晰模块边界降低贡献成本。

---

## 相关文档

- [产品定义](./00-product-definition.md)
- [设计原则](./01-design-principles.md)
- [ADR-0005 n8n 边界](../adr/0005-n8n-orchestration-boundary.md)
