# ADR-0005: n8n 编排边界 — 非核心 Runtime

## Status

Accepted

## Context

2024 年常见「AI 研究自动化」落地方式是以 **n8n**（或同类 iPaaS）为中心：

```text
Search → Download → Embedding → RAG → LLM → PDF
```

该模式适合演示与浅层流水线，但与 ResearchOS 目标冲突：

| 需求 | n8n 中心架构的问题 |
|------|-------------------|
| 动态重规划 / 反思环 | DAG/可视化节点难表达一等公民循环与策略分支 |
| Checkpoint / 审计回放 | 长任务状态、证据级恢复弱 |
| MCP 工具生态 | 节点与凭证绑定 UI，契约难标准化 |
| 多 Agent 督导 | Supervisor 语义需硬编码为巨型流 |
| 可测试性 | 复杂流难以单测与回归 |
| 知识进化 | 容易做成「跑完即弃」的会话管线 |

同时，n8n 在**调度、通知、企业系统胶水**方面仍有价值，团队中已有自动化经验也不应浪费。

需要清晰划定：**什么必须不在 n8n，什么可以在 n8n**。

## Decision

**n8n 不是 ResearchOS 的核心编排运行时。**

### 核心业务逻辑必须在

- **LangGraph Agent Runtime**（ADR-0001）
- **Python Agents**（Planner / Research / Reviewer / Writer / Memory）
- **MCP Tools**（ADR-0002）
- **Knowledge ETL & Hybrid RAG**（ADR-0003）

目标架构：

```text
Planner → Research → ETL → Knowledge Graph + Vector → Analysis Agents → Reviewer → Report
```

### n8n 仅允许的用途（Optional）

1. **调度**：Cron / Webhook 触发「创建研究任务」API。
2. **通知**：任务完成/失败推送邮件、企业微信、Slack 等。
3. **外围胶水**：与尚无 MCP Server 的遗留 IT 系统做过渡集成（应有淘汰计划）。
4. **运维类自动化**：备份提醒、健康检查告警（非研究语义）。

### 明确禁止

- 在 n8n 中实现研究状态机、反思环、Citation 组装主路径。
- 在 n8n 中直接串联 Embedding → RAG → 报告作为「官方研究架构」。
- 把 MCP Tool 调用权仅暴露给 n8n 而不暴露给 Runtime。
- 文档或营销将 ResearchOS 描述为「基于 n8n 的 Deep Research」。

### 集成方式

```text
n8n ──HTTP──► ResearchOS Gateway ──► LangGraph Runtime
  │                                        │
  └──── 等待回调 / 轮询任务状态 ◄──────────┘
              │
              ▼
         通知渠道
```

n8n 只看见 Gateway 的任务 API，不看见内部 Agent 图细节。

## Consequences

### 正面

- 架构叙事清晰，避免贡献者把 PR 做成「巨型 n8n JSON」。
- Runtime 可测试、可 Checkpoint、可私有审计。
- 仍保留自动化团队熟悉的调度/通知入口，降低迁移阻力。

### 负面 / 成本

- 需要提供稳定的「创建任务 / 查询状态 / Webhook 回调」API，供 n8n 使用。
- 习惯 n8n 编排 AI 的用户需要学习 Agent Runtime 概念（文档必须讲清）。

### 强制约束

- 仓库默认示例研究流必须是 Python/LangGraph；n8n 示例仅出现在 `deployment` / `integrations` 的 optional 目录。
- Code Review 若发现研究主路径逻辑进入 n8n，应按本 ADR 驳回或要求迁移。

## Alternatives Considered

| 方案 | 结论 |
|------|------|
| n8n 作为唯一编排器 | 否决：无法满足 Agent First / Checkpoint / MCP-Native |
| 完全禁止 n8n | 过严：损失调度通知场景的实用价值 |
| Temporal 取代 n8n 做外围 | 可作未来增强；不阻止 optional n8n |
| Airflow 做研究 DAG | 批处理友好，不适合交互式 HITL 研究主路径 |
