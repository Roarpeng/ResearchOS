# ADR-0007: 搜索路由器 — MCP Search Router

## Status

Accepted

## Context

Research Agent 需要从多种来源获取信息：

- 公开 Web 搜索
- 学术 / 预印本
- 专利与标准库
- 企业内部知识索引（Hybrid RAG）
- 代码与 Issue（GitHub 等）

若 Agent 直接绑定某一搜索供应商 SDK：

- 切换供应商成本高
- 难按查询类型与权限选择后端
- 速率限制、脱敏、审计逻辑重复
- 违背 MCP-Native（ADR-0002）

需要一个**统一搜索入口**，对 Agent 暴露稳定工具契约，对后端可插拔。

## Decision

实现 **Search Router** 作为一等 **MCP Server**（逻辑名 `search-router`）：

### Agent 可见工具（最小集）

| Tool | 作用 |
|------|------|
| `search.query` | 统一搜索：输入 query + 可选 filters/scope |
| `search.fetch` | 按结果 ID/URL 拉取规范化文档片段 |
| `search.explain_route` | （可选）返回路由决策，便于调试 |

### 路由逻辑（示意）

```text
Query + Context
    │
    ▼
Classifier / Rules
    ├── scope=internal → Hybrid RAG (Graph+Vector+Fulltext)
    ├── type=academic  → Academic providers
    ├── type=patent    → Patent providers
    ├── type=code      → Repo/GitHub search
    └── default        → Web search providers
    │
    ▼
Normalize hits → Rank/Merge → Return SearchHit[]
```

### 规范化命中结构（SearchHit）

```text
id, title, url/source_id, snippet, score, source_type, published_at?, raw_ref
```

### 策略要点

1. **多后端并行 + 融合**（可配置）；默认限制每后端 top-k。
2. **权限感知**：内部索引结果不得泄漏给无权限任务。
3. **Tool Budget**：Router 统计并强制搜索次数/拉取次数上限。
4. **可替换 Provider**：SerpAPI / Bing / SearxNG / 自建索引等经适配器接入，Agent 无感。
5. 与 Browser Tool 分工：Router 负责发现与轻量片段；深度阅读交给 `browser` MCP。

## Consequences

### 正面

- Research Agent Prompt/工具表稳定，后端可演进。
- 统一审计「搜了什么、命中了什么」。
- 内外部知识同一入口，利于混合研究。

### 负面 / 成本

- Router 成为关键路径，需要高可用与清晰降级（例如仅 internal）。
- 查询分类错误会导致召回来源偏差，需要日志与人工抽检。
- 各 Provider 归一化存在长期维护成本。

### 强制约束

- Research Agent 禁止直连具体搜索 SDK。
- 新增搜索源必须通过 Provider 适配器注册到 Router，而不是新造平行工具（除非新工具语义完全不同）。

## Alternatives Considered

| 方案 | 结论 |
|------|------|
| Agent 多工具直连各搜索 API | 契约爆炸，权限难管 |
| 仅企业内部 RAG，无 Web | 场景过窄，可作为部署裁剪而非架构默认 |
| 单一商业搜索 API | 供应商锁定，私有化差 |
| 让 n8n 做搜索聚合 | 否决为主路径（ADR-0005）；n8n 不可替代 Router |
| LangChain multi-retriever 内嵌 Runtime | 可作为实现细节，但对外仍应 MCP 化以便扩展 |
