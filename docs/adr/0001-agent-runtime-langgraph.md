# ADR-0001: Agent Runtime 选型 — LangGraph

## Status

Accepted

## Context

ResearchOS 的核心工作负载是**长时、多步、可中断**的深度研究：

- 动态规划与重规划（Planner）
- 多工具调用与并行子任务（Research）
- 反思 / 评审环（Reviewer）
- 人机确认（Human-in-the-loop）
- 失败恢复与审计回放（Checkpoint）

需要一个一等公民支持**有状态图执行**的 Runtime，而不是：

- 无状态 Request/Response 链
- 纯 DAG 工作流引擎（Airflow / n8n）表达 Agent 循环
- 单文件「Agent 框架脚本」难以生产化

约束：

- 主语言生态为 Python（FastAPI、解析器、数据层）
- 需与 MCP 工具调用、流式事件、PostgreSQL 持久化集成
- 团队需要可调试的显式状态（goal / plan / evidence / citations）

## Decision

采用 **LangGraph** 作为 ResearchOS 的 **Agent Runtime**：

1. 以 StateGraph 表达 Supervisor 与各子 Agent 节点及边条件。
2. 使用 Checkpointer 将 `TaskState` 持久化（默认 PostgreSQL）。
3. Gateway 仅负责鉴权与流式转发；**业务状态机不在 Gateway 内实现**。
4. 人机中断通过 graph interrupt / resume API 实现，与 Checkpoint 对齐。
5. 流式 token / 节点事件经 Runtime 发出，由 Gateway WebSocket/SSE 送达前端。

规范状态字段（最小集）：

```text
TaskState
├── goal
├── plan
├── evidence[]
├── citations[]
├── claims[]
├── critique
└── result / artifacts
```

## Consequences

### 正面

- 反思环、分支、重试具备清晰图语义。
- Checkpoint 使长任务可恢复、可审计。
- 与 LangChain 工具生态可互通，同时我们仍以 MCP 为工具主协议（见 ADR-0002）。
- 便于单测：可对节点函数与图边做确定性测试。

### 负面 / 成本

- 团队需掌握 LangGraph 状态归约与并发语义。
- 版本升级需关注 checkpoint schema 迁移。
- 过度复杂的图可能难读——需用 Supervisor 分层与子图约束复杂度。

### 强制约束

- 禁止在 n8n 中复制一套「研究状态机」。
- 禁止 Agent 业务代码绕过 Runtime 直接写「一次性脚本入口」作为生产路径。

## Alternatives Considered

| 方案 | 结论 |
|------|------|
| 纯 LangChain Agents / Chains | 状态与循环控制偏弱，生产检查点能力不如 LangGraph 一等公民 |
| AutoGen / CrewAI 等多 Agent 框架 | 适合原型；可控状态机、HITL、持久化与我们网关集成路径不如 LangGraph 清晰 |
| Temporal / Cadence 工作流 | 强可靠编排，但对 LLM Agent 的 fine-grained 图与流式体验偏重；可作未来「外包长任务」补充，不作核心 AI Runtime |
| 自研状态机 | 成本高，短期无收益 |
| n8n 作为 Runtime | 否决，见 ADR-0005 |
