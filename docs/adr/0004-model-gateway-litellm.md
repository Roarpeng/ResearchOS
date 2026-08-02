# ADR-0004: 模型网关 — LiteLLM

## Status

Accepted

## Context

ResearchOS 需要同时支持：

- 云端闭源模型（OpenAI、Claude、Gemini 等）
- 国产与开源 API（Qwen、DeepSeek 等）
- 本地推理（Ollama、vLLM 等）

不同 Agent 节点可能使用不同模型（规划用强推理模型，抽取用便宜快速模型，embedding 用专用模型）。若业务代码直连各厂商 SDK：

- 供应商锁定
- 限流、重试、fallback、成本统计重复实现
- 私有部署切换模型成本高

需要统一的 **Model Gateway**。

## Decision

采用 **LiteLLM** 作为 ResearchOS 的模型网关：

1. Runtime / Agents / ETL **只通过 LiteLLM**（或其兼容代理）访问 Chat / Embedding / Rerank（若适用）。
2. 模型以逻辑名配置（如 `planner`、`researcher`、`reviewer`、`embed`），映射到具体 provider/model。
3. 支持 fallback 链、超时、重试与基础用量日志。
4. API Key 仅配置在 Gateway/LiteLLM 侧，不进入 Agent Prompt 或前端。
5. 允许部署方禁用全部外网模型，仅保留本地端点（Private Deploy 降级模式）。

示例逻辑路由（示意）：

| 逻辑名 | 典型用途 |
|--------|----------|
| `model.planner` | 任务分解、重规划 |
| `model.researcher` | 阅读与证据抽取 |
| `model.reviewer` | 评审与矛盾检测 |
| `model.writer` | 报告润色与结构化 |
| `model.embed` | Chunk / 查询向量化 |

## Consequences

### 正面

- 满足「Model Independent」原则。
- 成本与故障切换集中治理。
- 便于 A/B：同一图换模型评测研究质量。

### 负面 / 成本

- 多一层代理，需监控其可用性。
- 厂商特有能力（某些 multimodal 参数）需在适配层显式声明，避免隐性依赖。
- LiteLLM 配置本身成为关键配置面，需要文档与示例。

### 强制约束

- 业务仓禁止大面积直依赖 `openai`/`anthropic` 官方 SDK 作为主路径（测试 mock 除外）。
- Embedding 与 Chat 路由必须可独立配置。

## Alternatives Considered

| 方案 | 结论 |
|------|------|
| 自研统一 SDK | 重复造轮，短期无必要 |
| 直连单一厂商 | 违背模型无关与私有部署 |
| OpenRouter 等托管聚合 | 可作为 LiteLLM 后端之一，但不作为唯一必选依赖 |
| 各 Agent 各自封装 Provider | 配置与可观测分裂 |
